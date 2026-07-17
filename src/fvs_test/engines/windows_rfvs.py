from __future__ import annotations

import shutil
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
from fvs_test.workspace import workspace_path


@dataclass(frozen=True)
class WindowsRFVSAdapter:
    definition: EngineDefinition

    def probe(self) -> EngineStatus:
        status = executable_status(self.definition)
        if not status.available:
            return status
        if self.definition.fvs_bin is None or not self.definition.fvs_bin.is_dir():
            return EngineStatus(
                self.definition.name,
                False,
                None,
                f"Windows FVS binary directory does not exist: {self.definition.fvs_bin}",
            )
        return EngineStatus(
            self.definition.name,
            True,
            None,
            f"Windows Rscript and FVS binaries found: {self.definition.fvs_bin}",
        )

    def validate(self, example: Example) -> None:
        validate_variant(self.definition, example)

    def command(self, request: RunRequest) -> tuple[str, ...]:
        fvs_bin = self.definition.fvs_bin
        if fvs_bin is None:
            raise EngineValidationError("Windows FVS binary directory is not configured")
        library_root = self.definition.executable.parents[2] / "library"
        try:
            return (
                str(self.definition.executable),
                "--vanilla",
                wsl_to_windows_path(request.workspace / "run_rfvs.R"),
                wsl_to_windows_path(
                    workspace_path(
                        request.workspace,
                        request.example,
                        request.example.keyfile,
                    )
                ),
                wsl_to_windows_path(fvs_bin),
                wsl_to_windows_path(library_root),
            )
        except ValueError as error:
            raise EngineValidationError(str(error)) from error

    def discover_outputs(self, workspace: Path) -> tuple[Path, ...]:
        return tuple(path for path in sorted(workspace.iterdir()) if path.is_file())

    def accepts_exit_code(self, exit_code: int) -> bool:
        return exit_code == 0

    def run(self, request: RunRequest) -> RunResult:
        from fvs_test.runner import run_engine

        shutil.copy2(_worker_source(), request.workspace / "run_rfvs.R")
        return run_engine(self, request)


def wsl_to_windows_path(path: Path) -> str:
    parts = path.resolve().parts
    if len(parts) < 4 or parts[1] != "mnt" or len(parts[2]) != 1:
        raise ValueError(f"path is not on a WSL mounted drive: {path}")
    drive = parts[2].upper()
    return f"{drive}:/{'/'.join(parts[3:])}"


def _worker_source() -> Path:
    return Path(__file__).with_name("run_rfvs.R")
