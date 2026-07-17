from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path


def _expected_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE summary (case_id TEXT, year INTEGER, volume REAL)"
        )
        connection.execute("INSERT INTO summary VALUES ('a', 2020, 100.0)")


def test_cli_runs_fake_native_engine_and_compares_database(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    example = repository / "examples" / "minimal"
    expected_directory = example / "expected"
    expected_directory.mkdir(parents=True)
    (example / "stand.key").write_text("STOP\n", encoding="utf-8")
    _expected_database(expected_directory / "expected.db")
    (example / "example.toml").write_text(
        'schema_version=1\nname="minimal"\ndescription="integration"\n'
        'variant="SN"\nkeyfile="stand.key"\n'
        'expected_db="expected/expected.db"\n'
        "[comparison]\ndefault_absolute_tolerance=0.0\n"
        "default_relative_tolerance=0.0\n"
        '[comparison.tables.summary]\nkeys=["case_id", "year"]\n',
        encoding="utf-8",
    )
    engine = repository / "fake-engine"
    engine.write_text(
        "#!/usr/bin/env python3\n"
        "import sqlite3\n"
        "with sqlite3.connect('output.db') as db:\n"
        "    db.execute('CREATE TABLE summary (case_id TEXT, year INTEGER, volume REAL)')\n"
        "    db.execute(\"INSERT INTO summary VALUES ('a', 2020, 100.0)\")\n"
        "print('fake engine complete')\n",
        encoding="utf-8",
    )
    engine.chmod(0o755)
    config = repository / "engines.toml"
    config.write_text(
        f'[engines.fake]\nadapter="native"\nexecutable="{engine}"\nvariants=["SN"]\n',
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "fvs_test.cli",
            "--repo-root",
            str(repository),
            "--engine-config",
            str(config),
            "run",
            "--engine",
            "fake",
            "--example",
            "minimal",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "status: success" in completed.stdout
    assert "comparison: equivalent" in completed.stdout
    records = list((repository / ".runs").glob("*/run.json"))
    assert len(records) == 1
