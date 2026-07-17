from __future__ import annotations

import shutil
from pathlib import Path

from fvs_test.models import Example


def create_workspace(runs_root: Path, run_id: str, example: Example) -> Path:
    workspace = runs_root.resolve() / run_id
    if workspace.exists():
        raise FileExistsError(f"run workspace already exists: {workspace}")
    workspace.mkdir(parents=True)
    for source in _engine_inputs(example):
        shutil.copy2(source, workspace / source.name)
    return workspace


def _engine_inputs(example: Example) -> tuple[Path, ...]:
    optional = (example.tree_data, example.input_db)
    return (example.keyfile, *(path for path in optional if path is not None))
