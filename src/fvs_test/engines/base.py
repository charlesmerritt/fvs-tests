from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from fvs_test.models import Example


class EngineValidationError(ValueError):
    pass


@dataclass(frozen=True)
class EngineDefinition:
    name: str
    adapter: str
    executable: Path
    project: Path | None = None
    fvs_bin: Path | None = None
    variants: tuple[str, ...] = ()


@dataclass(frozen=True)
class EngineStatus:
    name: str
    available: bool
    version: str | None
    diagnostic: str


class RunStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class RunResult:
    run_id: str
    engine: str
    adapter: str
    variant: str
    status: RunStatus
    command: tuple[str, ...]
    workspace: Path
    started_at: str
    elapsed_seconds: float
    exit_code: int | None
    stdout_path: Path
    stderr_path: Path
    artifacts: tuple[Path, ...]
    diagnostic: str | None
    record_path: Path


@dataclass(frozen=True)
class RunRequest:
    run_id: str
    engine: EngineDefinition
    example: Example
    workspace: Path
    timeout_seconds: float


class EngineCommand(Protocol):
    @property
    def definition(self) -> EngineDefinition: ...

    def command(self, request: RunRequest) -> tuple[str, ...]: ...

    def discover_outputs(self, workspace: Path) -> tuple[Path, ...]: ...

    def accepts_exit_code(self, exit_code: int) -> bool: ...


class EngineAdapter(EngineCommand, Protocol):
    def probe(self) -> EngineStatus: ...

    def validate(self, example: Example) -> None: ...

    def run(self, request: RunRequest) -> RunResult: ...


def executable_status(definition: EngineDefinition) -> EngineStatus:
    executable = definition.executable
    if not executable.is_file() or not os.access(executable, os.X_OK):
        return EngineStatus(
            definition.name,
            False,
            None,
            f"executable is missing or not executable: {executable}",
        )
    return EngineStatus(definition.name, True, None, f"executable found: {executable}")


def validate_variant(definition: EngineDefinition, example: Example) -> None:
    if definition.variants and example.variant not in definition.variants:
        supported = ", ".join(definition.variants)
        raise EngineValidationError(
            f"engine {definition.name} does not support variant {example.variant}; "
            f"supported: {supported}"
        )
