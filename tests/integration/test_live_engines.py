from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from fvs_test.cli import main


REPO_ROOT = Path(__file__).parents[2]
LIVE_ENABLED = os.environ.get("FVS_TEST_LIVE") == "1"
WINDOWS_RUNS_ROOT = os.environ.get("FVS_TEST_WINDOWS_RUNS_ROOT")


def _run(engine: str, runs_root: Path) -> Path:
    exit_code = main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--runs-root",
            str(runs_root),
            "run",
            "--engine",
            engine,
            "--example",
            "thinba",
            "--timeout",
            "120",
        ]
    )
    assert exit_code == 0
    workspaces = tuple(runs_root.iterdir())
    assert len(workspaces) == 1
    return workspaces[0]


@pytest.mark.live_engine
@pytest.mark.skipif(not LIVE_ENABLED, reason="set FVS_TEST_LIVE=1 to run engines")
def test_fvsjl_cli_runs_thinba(tmp_path: Path) -> None:
    workspace = _run("fvsjl", tmp_path / "runs")

    assert (workspace / "fvsjl.sum").is_file()
    assert (workspace / "run.json").is_file()


@pytest.mark.live_engine
@pytest.mark.skipif(not LIVE_ENABLED, reason="set FVS_TEST_LIVE=1 to run engines")
def test_official_native_cli_runs_thinba(tmp_path: Path) -> None:
    workspace = _run("official-sn", tmp_path / "runs")

    assert (workspace / "thinba.out").is_file()
    assert (workspace / "run.json").is_file()


@pytest.mark.live_engine
@pytest.mark.skipif(
    not LIVE_ENABLED or WINDOWS_RUNS_ROOT is None,
    reason="set FVS_TEST_LIVE=1 and FVS_TEST_WINDOWS_RUNS_ROOT to run Windows rFVS",
)
def test_windows_rfvs_cli_runs_thinba() -> None:
    assert WINDOWS_RUNS_ROOT is not None
    runs_root = Path(WINDOWS_RUNS_ROOT) / f"pytest-{uuid4().hex}"
    workspace = _run("windows-rfvs", runs_root)

    assert (workspace / "thinba.out").is_file()
    assert (workspace / "run.json").is_file()
