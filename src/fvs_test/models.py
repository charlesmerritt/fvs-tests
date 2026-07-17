from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Tolerance:
    absolute: float = 1.0e-6
    relative: float = 1.0e-6

    def __post_init__(self) -> None:
        if self.absolute < 0 or self.relative < 0:
            raise ValueError("tolerances must be non-negative")


@dataclass(frozen=True)
class TablePolicy:
    keys: tuple[str, ...]
    ignore_columns: tuple[str, ...] = ()
    tolerances: dict[str, Tolerance] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.keys:
            raise ValueError("table comparison keys must not be empty")


@dataclass(frozen=True)
class ComparisonPolicy:
    default_tolerance: Tolerance = Tolerance()
    tables: dict[str, TablePolicy] = field(default_factory=dict)


@dataclass(frozen=True)
class Example:
    name: str
    description: str
    variant: str
    root: Path
    keyfile: Path
    tree_data: Path | None
    input_db: Path | None
    expected_db: Path | None
    comparison: ComparisonPolicy
