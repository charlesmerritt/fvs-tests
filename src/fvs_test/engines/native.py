from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fvs_test.engines.base import (
    EngineDefinition,
    EngineStatus,
    RunRequest,
    executable_status,
    validate_variant,
)
from fvs_test.models import Example


@dataclass(frozen=True)
class NativeAdapter:
    definition: EngineDefinition

    def probe(self) -> EngineStatus:
        return executable_status(self.definition)

    def validate(self, example: Example) -> None:
        validate_variant(self.definition, example)

    def command(self, request: RunRequest) -> tuple[str, ...]:
        keyword_file = request.workspace / request.example.keyfile.name
        return (str(self.definition.executable), f"--keywordfile={keyword_file}")

    def discover_outputs(self, workspace: Path) -> tuple[Path, ...]:
        return tuple(
            path
            for path in sorted(workspace.iterdir())
            if path.is_file() and path.suffix.lower() in {".csv", ".db", ".out", ".sum"}
        )
