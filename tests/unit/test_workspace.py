from importlib import import_module
from pathlib import Path

import pytest

from fvs_test.catalog import load_example


FIXTURE = Path(__file__).parents[1] / "fixtures" / "examples" / "minimal"


def test_workspace_copies_declared_engine_inputs(tmp_path: Path) -> None:
    workspace = import_module("fvs_test.workspace")
    example = load_example(FIXTURE)

    run_directory = workspace.create_workspace(tmp_path, "run-1", example)

    assert (run_directory / "stand.key").read_text() == example.keyfile.read_text()
    assert example.tree_data is not None
    assert (run_directory / "stand.tre").read_text() == example.tree_data.read_text()
    assert sorted(path.name for path in run_directory.iterdir()) == [
        "stand.key",
        "stand.tre",
    ]


def test_workspace_rejects_existing_run_id(tmp_path: Path) -> None:
    workspace = import_module("fvs_test.workspace")
    (tmp_path / "run-1").mkdir()

    with pytest.raises(FileExistsError, match="run workspace already exists"):
        workspace.create_workspace(tmp_path, "run-1", load_example(FIXTURE))


def test_workspace_preserves_nested_asset_paths(tmp_path: Path) -> None:
    workspace = import_module("fvs_test.workspace")
    example_root = tmp_path / "example"
    (example_root / "controls").mkdir(parents=True)
    (example_root / "data").mkdir()
    (example_root / "controls" / "stand.key").write_text(
        "TREEDATA data/stand.tre\n",
        encoding="utf-8",
    )
    (example_root / "data" / "stand.tre").write_text("tree data\n", encoding="utf-8")
    (example_root / "example.toml").write_text(
        'schema_version=1\nname="nested"\ndescription="nested assets"\n'
        'variant="SN"\nkeyfile="controls/stand.key"\n'
        'tree_data="data/stand.tre"\n',
        encoding="utf-8",
    )

    run_directory = workspace.create_workspace(
        tmp_path / "runs",
        "run-1",
        load_example(example_root),
    )

    assert (run_directory / "controls" / "stand.key").is_file()
    assert (run_directory / "data" / "stand.tre").is_file()
    assert not (run_directory / "stand.key").exists()
