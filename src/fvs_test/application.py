from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fvs_test.catalog import load_examples
from fvs_test.comparison import (
    ComparisonResult,
    compare_databases,
    write_comparison,
)
from fvs_test.config import load_engine_definitions
from fvs_test.engines import create_adapter
from fvs_test.engines.base import (
    EngineDefinition,
    EngineStatus,
    RunRequest,
    RunResult,
    RunStatus,
)
from fvs_test.models import Example
from fvs_test.workspace import create_workspace


class ApplicationError(RuntimeError):
    pass


@dataclass(frozen=True)
class RunOutcome:
    run: RunResult
    comparison: ComparisonResult | None


@dataclass(frozen=True)
class Application:
    engines: dict[str, EngineDefinition]
    examples: dict[str, Example]
    runs_root: Path

    @classmethod
    def from_paths(
        cls,
        repo_root: Path,
        engine_config: Path,
        local_config: Path | None,
        runs_root: Path,
    ) -> Application:
        return cls(
            load_engine_definitions(engine_config, local_config),
            load_examples(repo_root / "examples"),
            runs_root,
        )

    def engine_statuses(self) -> tuple[EngineStatus, ...]:
        return tuple(
            create_adapter(self._engine(name)).probe() for name in sorted(self.engines)
        )

    def example_catalog(self) -> tuple[Example, ...]:
        return tuple(self.examples[name] for name in sorted(self.examples))

    def run(self, engine_name: str, example_name: str, timeout: float) -> RunOutcome:
        definition = self._engine(engine_name)
        example = self._example(example_name)
        adapter = create_adapter(definition)
        status = adapter.probe()
        if not status.available:
            raise ApplicationError(
                f"engine {engine_name} is unavailable: {status.diagnostic}"
            )
        adapter.validate(example)

        run_id = _run_id(engine_name, example_name)
        workspace = create_workspace(self.runs_root, run_id, example)
        result = adapter.run(
            RunRequest(run_id, definition, example, workspace, timeout)
        )
        if result.status is not RunStatus.SUCCESS or example.expected_db is None:
            return RunOutcome(result, None)

        actual = _output_database(result, example)
        comparison = compare_databases(actual, example.expected_db, example.comparison)
        write_comparison(comparison, workspace / "comparison.json")
        return RunOutcome(result, comparison)

    def compare(
        self,
        example_name: str,
        actual: Path,
        expected: Path | None,
    ) -> ComparisonResult:
        example = self._example(example_name)
        baseline = expected or example.expected_db
        if baseline is None:
            raise ApplicationError(f"example {example_name} has no expected database")
        return compare_databases(actual, baseline, example.comparison)

    def _engine(self, name: str):
        try:
            return self.engines[name]
        except KeyError as error:
            raise ApplicationError(f"unknown engine: {name}") from error

    def _example(self, name: str) -> Example:
        try:
            return self.examples[name]
        except KeyError as error:
            raise ApplicationError(f"unknown example: {name}") from error


def _run_id(engine: str, example: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{engine}-{example}-{uuid4().hex[:8]}"


def _output_database(result: RunResult, example: Example) -> Path:
    input_name = example.input_db.name if example.input_db is not None else None
    databases = tuple(
        path
        for path in result.artifacts
        if path.suffix.lower() == ".db" and path.name != input_name
    )
    if not databases:
        raise ApplicationError(
            f"run succeeded but produced no output database; workspace: {result.workspace}"
        )
    if len(databases) > 1:
        names = ", ".join(path.name for path in databases)
        raise ApplicationError(
            f"run produced multiple output databases ({names}); workspace: {result.workspace}"
        )
    return databases[0]
