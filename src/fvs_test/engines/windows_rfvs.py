from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fvs_test.engines.base import (
    EngineDefinition,
    EngineStatus,
    EngineValidationError,
    RunRequest,
    executable_status,
    validate_variant,
)
from fvs_test.models import Example


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
        raise EngineValidationError(
            "Windows rFVS execution wrapper is not configured yet"
        )

    def discover_outputs(self, workspace: Path) -> tuple[Path, ...]:
        return tuple(path for path in sorted(workspace.iterdir()) if path.is_file())


def wsl_to_windows_path(path: Path) -> str:
    parts = path.resolve().parts
    if len(parts) < 4 or parts[1] != "mnt" or len(parts[2]) != 1:
        raise ValueError(f"path is not on a WSL mounted drive: {path}")
    drive = parts[2].upper()
    return f"{drive}:/{'/'.join(parts[3:])}"
