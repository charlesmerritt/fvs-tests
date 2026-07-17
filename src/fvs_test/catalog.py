from __future__ import annotations

import tomllib
from pathlib import Path
from collections.abc import Mapping
from typing import Any, cast

from fvs_test.models import (
    ComparisonPolicy,
    Example,
    TablePolicy,
    Tolerance,
)


class CatalogError(ValueError):
    pass


def load_example(path: Path) -> Example:
    root = path.resolve()
    manifest = root / "example.toml"
    if not manifest.is_file():
        raise CatalogError(f"example manifest does not exist: {manifest}")

    with manifest.open("rb") as stream:
        document = tomllib.load(stream)
    if document.get("schema_version") != 1:
        raise CatalogError("example schema_version must be 1")

    return Example(
        name=_required_string(document, "name"),
        description=_required_string(document, "description"),
        variant=_required_string(document, "variant").upper(),
        root=root,
        keyfile=_asset(root, _required_string(document, "keyfile")),
        tree_data=_optional_asset(root, document.get("tree_data")),
        input_db=_optional_asset(root, document.get("input_db")),
        expected_db=_optional_asset(root, document.get("expected_db")),
        comparison=_comparison_policy(document.get("comparison", {})),
    )


def load_examples(root: Path) -> dict[str, Example]:
    examples: dict[str, Example] = {}
    if not root.is_dir():
        return examples
    for manifest in sorted(root.glob("*/example.toml")):
        example = load_example(manifest.parent)
        if example.name in examples:
            raise CatalogError(f"duplicate example name: {example.name}")
        examples[example.name] = example
    return examples


def _required_string(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"example {key} must be a non-empty string")
    return value


def _optional_asset(root: Path, value: object) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise CatalogError("asset path must be a non-empty string")
    return _asset(root, value)


def _asset(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise CatalogError(f"asset path escapes example directory: {relative_path}")
    if not candidate.is_file():
        raise CatalogError(f"example asset does not exist: {relative_path}")
    return candidate


def _comparison_policy(value: object) -> ComparisonPolicy:
    document = _string_mapping(value, "comparison")
    absolute = _number(document, "default_absolute_tolerance", 1.0e-6)
    relative = _number(document, "default_relative_tolerance", 1.0e-6)
    raw_tables = _string_mapping(document.get("tables", {}), "comparison.tables")
    tables = {
        name: _table_policy(name, table) for name, table in sorted(raw_tables.items())
    }
    return ComparisonPolicy(Tolerance(absolute, relative), tables)


def _table_policy(name: str, value: object) -> TablePolicy:
    document = _string_mapping(value, f"comparison table {name}")
    keys = _string_tuple(document.get("keys"), f"comparison table {name} keys")
    ignored = _string_tuple(
        document.get("ignore_columns", []),
        f"comparison table {name} ignore_columns",
        allow_empty=True,
    )
    raw_tolerances = _string_mapping(
        document.get("tolerances", {}),
        f"comparison table {name} tolerances",
    )
    tolerances = {
        column: _tolerance(name, column, tolerance)
        for column, tolerance in sorted(raw_tolerances.items())
    }
    return TablePolicy(keys, ignored, tolerances)


def _tolerance(table: str, column: str, value: object) -> Tolerance:
    document = _string_mapping(value, f"tolerance for {table}.{column}")
    return Tolerance(
        _number(document, "absolute", 1.0e-6),
        _number(document, "relative", 1.0e-6),
    )


def _number(document: Mapping[str, object], key: str, default: float) -> float:
    value = document.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CatalogError(f"{key} must be numeric")
    return float(value)


def _string_tuple(
    value: object, label: str, *, allow_empty: bool = False
) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise CatalogError(f"{label} must be a list of non-empty strings")
    if not value and not allow_empty:
        raise CatalogError(f"{label} must not be empty")
    return tuple(item for item in value if isinstance(item, str))


def _string_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise CatalogError(f"{label} must be a TOML table")
    return cast(dict[str, Any], value)
