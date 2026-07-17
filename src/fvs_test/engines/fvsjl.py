from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fvs_test.engines.base import (
    EngineDefinition,
    EngineStatus,
    EngineValidationError,
    RunRequest,
    RunResult,
    executable_status,
    validate_variant,
)
from fvs_test.models import Example


@dataclass(frozen=True)
class FVSjlAdapter:
    definition: EngineDefinition

    def probe(self) -> EngineStatus:
        status = executable_status(self.definition)
        if not status.available:
            return status
        script = self._script()
        if not script.is_file():
            return EngineStatus(
                self.definition.name,
                False,
                None,
                f"FVSjl CLI does not exist: {script}",
            )
        return EngineStatus(
            self.definition.name,
            True,
            None,
            f"Julia and FVSjl CLI found: {script}",
        )

    def validate(self, example: Example) -> None:
        validate_variant(self.definition, example)
        if example.keyfile.suffix.lower() not in {".key", ".yaml", ".yml"}:
            raise EngineValidationError("FVSjl requires a .key or YAML keyword file")

    def command(self, request: RunRequest) -> tuple[str, ...]:
        project = self._project()
        keyword_file = request.workspace / request.example.keyfile.name
        return (
            str(self.definition.executable),
            f"--project={project}",
            str(self._script()),
            str(keyword_file),
            f"--variant={request.example.variant}",
            "-o",
            str(request.workspace / "fvsjl.sum"),
        )

    def discover_outputs(self, workspace: Path) -> tuple[Path, ...]:
        return tuple(
            path
            for path in sorted(workspace.iterdir())
            if path.is_file() and path.suffix.lower() in {".csv", ".db", ".sum"}
        )

    def accepts_exit_code(self, exit_code: int) -> bool:
        return exit_code == 0

    def run(self, request: RunRequest) -> RunResult:
        from fvs_test.runner import run_engine

        return run_engine(self, request)

    def _project(self) -> Path:
        if self.definition.project is None:
            raise EngineValidationError("FVSjl project path is not configured")
        return self.definition.project

    def _script(self) -> Path:
        return self._project() / "bin" / "fvsjl-run.jl"
