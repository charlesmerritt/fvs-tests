from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from fvs_test.catalog import load_example
from fvs_test.comparison import ComparisonResult, Difference
from fvs_test.engines.base import EngineStatus, RunStatus


FIXTURE = Path(__file__).parents[1] / "fixtures" / "examples" / "minimal"


class FakeApplication:
    def __init__(
        self, *, run_status: RunStatus = RunStatus.SUCCESS, equivalent: bool = True
    ):
        self.run_status = run_status
        self.equivalent = equivalent

    def engine_statuses(self) -> tuple[EngineStatus, ...]:
        return (EngineStatus("fake", True, "1.0", "ready"),)

    def example_catalog(self) -> tuple[object, ...]:
        return (load_example(FIXTURE),)

    def run(self, engine_name: str, example_name: str, timeout: float) -> object:
        run = SimpleNamespace(
            status=self.run_status,
            workspace=Path("/tmp/run-1"),
            diagnostic="failed" if self.run_status is RunStatus.FAILED else None,
        )
        comparison = (
            self._comparison() if self.run_status is RunStatus.SUCCESS else None
        )
        return SimpleNamespace(run=run, comparison=comparison)

    def compare(
        self, example_name: str, actual: Path, expected: Path | None
    ) -> ComparisonResult:
        return self._comparison()

    def _comparison(self) -> ComparisonResult:
        differences = () if self.equivalent else (Difference("value", "summary"),)
        return ComparisonResult(
            self.equivalent, Path("actual.db"), Path("expected.db"), differences
        )


def test_parser_exposes_top_level_commands() -> None:
    cli = import_module("fvs_test.cli")

    parser = cli.build_parser()

    action = next(action for action in parser._actions if action.dest == "command")
    assert action.choices is not None
    assert set(action.choices) == {"engines", "examples", "run", "compare"}


def test_engines_prints_probe_status(capsys: Any) -> None:
    cli = import_module("fvs_test.cli")

    exit_code = cli.main(["engines"], application=cast(Any, FakeApplication()))

    assert exit_code == 0
    assert capsys.readouterr().out == "fake\tavailable\t1.0\tready\n"


def test_failed_run_returns_one_and_prints_workspace(capsys: Any) -> None:
    cli = import_module("fvs_test.cli")

    exit_code = cli.main(
        ["run", "--engine", "fake", "--example", "minimal"],
        application=cast(Any, FakeApplication(run_status=RunStatus.FAILED)),
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "workspace: /tmp/run-1" in output
    assert "status: failed" in output


def test_comparison_mismatch_returns_one(capsys: Any) -> None:
    cli = import_module("fvs_test.cli")

    exit_code = cli.main(
        ["compare", "--example", "minimal", "--actual", "actual.db"],
        application=cast(Any, FakeApplication(equivalent=False)),
    )

    assert exit_code == 1
    assert "comparison: different" in capsys.readouterr().out
