from __future__ import annotations

import sqlite3
from importlib import import_module
from pathlib import Path

import pytest

from fvs_test.models import ComparisonPolicy, TablePolicy, Tolerance


def _database(
    path: Path,
    rows: list[tuple[object, ...]],
    *,
    extra_column: bool = False,
) -> Path:
    extra_schema = ", extra TEXT" if extra_column else ""
    placeholders = ", ?" if extra_column else ""
    values = [(*row, "extra") if extra_column else row for row in rows]
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE summary ("
            "case_id TEXT, year INTEGER, volume REAL, label TEXT, generated_at TEXT"
            f"{extra_schema})"
        )
        connection.executemany(
            f"INSERT INTO summary VALUES (?, ?, ?, ?, ?{placeholders})",
            values,
        )
    return path


def _policy(*, absolute: float = 0.0, relative: float = 0.0) -> ComparisonPolicy:
    return ComparisonPolicy(
        Tolerance(absolute, relative),
        {
            "summary": TablePolicy(
                ("case_id", "year"),
                ("generated_at",),
                {"volume": Tolerance(1.0, 0.001)},
            )
        },
    )


def test_equal_content_ignores_declared_volatile_column(tmp_path: Path) -> None:
    comparison = import_module("fvs_test.comparison")
    expected = _database(tmp_path / "expected.db", [("a", 2020, 100.0, "pine", "old")])
    actual = _database(tmp_path / "actual.db", [("a", 2020, 100.0, "pine", "new")])

    result = comparison.compare_databases(actual, expected, _policy())

    assert result.equivalent is True
    assert result.differences == ()


def test_numeric_value_within_column_tolerance_is_equal(tmp_path: Path) -> None:
    comparison = import_module("fvs_test.comparison")
    expected = _database(tmp_path / "expected.db", [("a", 2020, 100.0, "pine", "x")])
    actual = _database(tmp_path / "actual.db", [("a", 2020, 100.5, "pine", "x")])

    result = comparison.compare_databases(actual, expected, _policy())

    assert result.equivalent is True


def test_numeric_value_outside_tolerance_reports_difference(tmp_path: Path) -> None:
    comparison = import_module("fvs_test.comparison")
    expected = _database(tmp_path / "expected.db", [("a", 2020, 100.0, "pine", "x")])
    actual = _database(tmp_path / "actual.db", [("a", 2020, 102.0, "pine", "x")])

    result = comparison.compare_databases(actual, expected, _policy())

    assert result.equivalent is False
    difference = result.differences[0]
    assert difference.kind == "value"
    assert difference.table == "summary"
    assert difference.column == "volume"
    assert difference.absolute_difference == 2.0


def test_missing_row_is_reported_once(tmp_path: Path) -> None:
    comparison = import_module("fvs_test.comparison")
    expected = _database(
        tmp_path / "expected.db",
        [("a", 2020, 100.0, "pine", "x"), ("b", 2020, 80.0, "oak", "x")],
    )
    actual = _database(tmp_path / "actual.db", [("a", 2020, 100.0, "pine", "x")])

    result = comparison.compare_databases(actual, expected, _policy())

    assert [difference.kind for difference in result.differences] == ["row"]


def test_missing_table_and_extra_column_are_explicit(tmp_path: Path) -> None:
    comparison = import_module("fvs_test.comparison")
    expected = _database(tmp_path / "expected.db", [("a", 2020, 100.0, "pine", "x")])
    empty = tmp_path / "empty.db"
    with sqlite3.connect(empty):
        pass
    missing = comparison.compare_databases(empty, expected, _policy())

    actual = _database(
        tmp_path / "actual.db",
        [("a", 2020, 100.0, "pine", "x")],
        extra_column=True,
    )
    schema = comparison.compare_databases(actual, expected, _policy())

    assert [difference.kind for difference in missing.differences] == ["table"]
    assert [difference.kind for difference in schema.differences] == ["column"]
    assert schema.differences[0].column == "extra"


def test_null_mismatch_is_not_equal(tmp_path: Path) -> None:
    comparison = import_module("fvs_test.comparison")
    expected = _database(tmp_path / "expected.db", [("a", 2020, 100.0, None, "x")])
    actual = _database(tmp_path / "actual.db", [("a", 2020, 100.0, "pine", "x")])

    result = comparison.compare_databases(actual, expected, _policy())

    assert result.equivalent is False
    assert result.differences[0].column == "label"


def test_duplicate_keys_are_rejected(tmp_path: Path) -> None:
    comparison = import_module("fvs_test.comparison")
    expected = _database(
        tmp_path / "expected.db",
        [("a", 2020, 100.0, "pine", "x"), ("a", 2020, 101.0, "pine", "x")],
    )
    actual = _database(tmp_path / "actual.db", [("a", 2020, 100.0, "pine", "x")])

    with pytest.raises(comparison.ComparisonError, match="duplicate key"):
        comparison.compare_databases(actual, expected, _policy())


def test_empty_comparison_policy_is_rejected(tmp_path: Path) -> None:
    comparison = import_module("fvs_test.comparison")
    expected = _database(tmp_path / "expected.db", [("a", 2020, 100.0, "pine", "x")])
    actual = _database(tmp_path / "actual.db", [("a", 2020, 100.0, "pine", "x")])

    with pytest.raises(comparison.ComparisonError, match="at least one table"):
        comparison.compare_databases(actual, expected, ComparisonPolicy())
