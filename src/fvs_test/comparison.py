from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import duckdb

from fvs_test.models import ComparisonPolicy, TablePolicy, Tolerance


class ComparisonError(ValueError):
    pass


@dataclass(frozen=True)
class Difference:
    kind: str
    table: str
    row_key: str | None = None
    column: str | None = None
    expected: object = None
    actual: object = None
    absolute_difference: float | None = None
    relative_difference: float | None = None


@dataclass(frozen=True)
class ComparisonResult:
    equivalent: bool
    actual: Path
    expected: Path
    differences: tuple[Difference, ...]

    def counts(self) -> dict[str, int]:
        return dict(sorted(Counter(item.kind for item in self.differences).items()))


@dataclass(frozen=True)
class Cell:
    source: str
    table_name: str
    row_key: str
    column_name: str
    value_kind: str
    text_value: str | None
    numeric_value: float | None


@dataclass(frozen=True)
class TableSnapshot:
    columns: frozenset[str]
    row_keys: frozenset[str]
    cells: tuple[Cell, ...]


def compare_databases(
    actual: Path,
    expected: Path,
    policy: ComparisonPolicy,
) -> ComparisonResult:
    differences: list[Difference] = []
    cells: list[Cell] = []
    with _open_readonly(actual) as actual_db, _open_readonly(expected) as expected_db:
        actual_tables = _table_names(actual_db)
        expected_tables = _table_names(expected_db)
        for table, table_policy in sorted(policy.tables.items()):
            if table not in actual_tables or table not in expected_tables:
                differences.append(
                    Difference(
                        "table",
                        table,
                        expected=table in expected_tables,
                        actual=table in actual_tables,
                    )
                )
                continue
            actual_snapshot = _load_table(actual_db, "actual", table, table_policy)
            expected_snapshot = _load_table(
                expected_db, "expected", table, table_policy
            )
            differences.extend(
                _schema_differences(table, actual_snapshot, expected_snapshot)
            )
            differences.extend(
                _row_differences(table, actual_snapshot, expected_snapshot)
            )
            cells.extend(actual_snapshot.cells)
            cells.extend(expected_snapshot.cells)

    differences.extend(_value_differences(cells, policy))
    ordered = tuple(
        sorted(
            differences,
            key=lambda item: (
                item.table,
                item.kind,
                item.row_key or "",
                item.column or "",
            ),
        )
    )
    return ComparisonResult(not ordered, actual.resolve(), expected.resolve(), ordered)


def write_comparison(result: ComparisonResult, path: Path) -> Path:
    payload = {
        "equivalent": result.equivalent,
        "actual": str(result.actual),
        "expected": str(result.expected),
        "counts": result.counts(),
        "differences": [asdict(difference) for difference in result.differences],
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def _open_readonly(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise ComparisonError(f"SQLite database does not exist: {path}")
    return sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)


def _table_names(connection: sqlite3.Connection) -> frozenset[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return frozenset(str(row[0]) for row in rows)


def _load_table(
    connection: sqlite3.Connection,
    source: str,
    table: str,
    policy: TablePolicy,
) -> TableSnapshot:
    quoted_table = _quote_identifier(table)
    metadata = connection.execute(f"PRAGMA table_info({quoted_table})").fetchall()
    columns = tuple(str(row[1]) for row in metadata)
    missing_keys = set(policy.keys).difference(columns)
    if missing_keys:
        raise ComparisonError(
            f"table {table} is missing key columns: {sorted(missing_keys)}"
        )

    rows = connection.execute(f"SELECT * FROM {quoted_table}").fetchall()
    indexes = {column: index for index, column in enumerate(columns)}
    row_keys: set[str] = set()
    cells: list[Cell] = []
    for row in rows:
        row_key = json.dumps(
            {key: row[indexes[key]] for key in policy.keys},
            sort_keys=True,
            separators=(",", ":"),
        )
        if row_key in row_keys:
            raise ComparisonError(f"duplicate key in {source}.{table}: {row_key}")
        row_keys.add(row_key)
        for column in columns:
            if column in policy.keys or column in policy.ignore_columns:
                continue
            cells.append(_cell(source, table, row_key, column, row[indexes[column]]))
    compared_columns = frozenset(columns).difference(policy.ignore_columns)
    return TableSnapshot(compared_columns, frozenset(row_keys), tuple(cells))


def _cell(
    source: str,
    table: str,
    row_key: str,
    column: str,
    value: object,
) -> Cell:
    if value is None:
        return Cell(source, table, row_key, column, "null", None, None)
    if isinstance(value, float):
        return Cell(source, table, row_key, column, "real", None, value)
    if isinstance(value, int):
        return Cell(source, table, row_key, column, "integer", str(value), None)
    if isinstance(value, bytes):
        return Cell(source, table, row_key, column, "blob", value.hex(), None)
    return Cell(source, table, row_key, column, "text", str(value), None)


def _schema_differences(
    table: str,
    actual: TableSnapshot,
    expected: TableSnapshot,
) -> list[Difference]:
    return [
        Difference(
            "column",
            table,
            column=column,
            expected=column in expected.columns,
            actual=column in actual.columns,
        )
        for column in sorted(actual.columns.symmetric_difference(expected.columns))
    ]


def _row_differences(
    table: str,
    actual: TableSnapshot,
    expected: TableSnapshot,
) -> list[Difference]:
    return [
        Difference(
            "row",
            table,
            row_key=row_key,
            expected=row_key in expected.row_keys,
            actual=row_key in actual.row_keys,
        )
        for row_key in sorted(actual.row_keys.symmetric_difference(expected.row_keys))
    ]


def _value_differences(
    cells: list[Cell],
    policy: ComparisonPolicy,
) -> list[Difference]:
    if not cells:
        return []
    connection = duckdb.connect(":memory:")
    try:
        connection.execute(
            """
            CREATE TABLE cells (
                source VARCHAR,
                table_name VARCHAR,
                row_key VARCHAR,
                column_name VARCHAR,
                value_kind VARCHAR,
                text_value VARCHAR,
                numeric_value DOUBLE
            )
            """
        )
        connection.executemany(
            "INSERT INTO cells VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    cell.source,
                    cell.table_name,
                    cell.row_key,
                    cell.column_name,
                    cell.value_kind,
                    cell.text_value,
                    cell.numeric_value,
                )
                for cell in cells
            ],
        )
        joined = connection.execute(
            """
            SELECT
                expected.table_name,
                expected.row_key,
                expected.column_name,
                expected.value_kind,
                expected.text_value,
                expected.numeric_value,
                actual.value_kind,
                actual.text_value,
                actual.numeric_value
            FROM cells AS expected
            INNER JOIN cells AS actual
                USING (table_name, row_key, column_name)
            WHERE expected.source = 'expected' AND actual.source = 'actual'
            ORDER BY expected.table_name, expected.row_key, expected.column_name
            """
        ).fetchall()
    finally:
        connection.close()

    return [
        difference
        for row in joined
        if (difference := _joined_difference(row, policy)) is not None
    ]


def _joined_difference(
    row: tuple[Any, ...],
    policy: ComparisonPolicy,
) -> Difference | None:
    table, row_key, column = (str(row[0]), str(row[1]), str(row[2]))
    expected_kind, expected_text, expected_numeric = row[3:6]
    actual_kind, actual_text, actual_numeric = row[6:9]
    if expected_kind != actual_kind:
        return Difference(
            "value",
            table,
            row_key,
            column,
            _value(expected_kind, expected_text, expected_numeric),
            _value(actual_kind, actual_text, actual_numeric),
        )
    if expected_kind != "real":
        if expected_text == actual_text:
            return None
        return Difference("value", table, row_key, column, expected_text, actual_text)

    expected_number = float(expected_numeric)
    actual_number = float(actual_numeric)
    absolute = abs(actual_number - expected_number)
    relative = absolute / abs(expected_number) if expected_number else None
    tolerance = _tolerance(policy, table, column)
    allowed = tolerance.absolute + tolerance.relative * abs(expected_number)
    if absolute <= allowed:
        return None
    return Difference(
        "value",
        table,
        row_key,
        column,
        expected_number,
        actual_number,
        absolute,
        relative,
    )


def _tolerance(policy: ComparisonPolicy, table: str, column: str) -> Tolerance:
    return policy.tables[table].tolerances.get(column, policy.default_tolerance)


def _value(kind: object, text: object, numeric: object) -> object:
    if kind == "null":
        return None
    if kind == "real":
        return numeric
    return text


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
