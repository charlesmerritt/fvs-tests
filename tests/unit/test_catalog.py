from importlib import import_module
from pathlib import Path

import pytest


FIXTURES = Path(__file__).parents[1] / "fixtures" / "examples"


def test_load_example_resolves_declared_assets() -> None:
    catalog = import_module("fvs_test.catalog")

    example = catalog.load_example(FIXTURES / "minimal")

    assert example.name == "minimal"
    assert example.variant == "SN"
    assert example.keyfile.name == "stand.key"
    assert example.tree_data is not None
    assert example.comparison.tables["summary"].keys == ("case_id", "year")
    assert example.comparison.tables["summary"].tolerances["volume"].absolute == 1.0


def test_load_example_rejects_missing_asset(tmp_path: Path) -> None:
    catalog = import_module("fvs_test.catalog")
    (tmp_path / "example.toml").write_text(
        'schema_version=1\nname="bad"\ndescription="bad"\n'
        'variant="SN"\nkeyfile="missing.key"\n',
        encoding="utf-8",
    )

    with pytest.raises(catalog.CatalogError, match="does not exist"):
        catalog.load_example(tmp_path)


def test_load_example_rejects_path_escape(tmp_path: Path) -> None:
    catalog = import_module("fvs_test.catalog")
    outside = tmp_path.parent / "outside.key"
    outside.write_text("STOP\n", encoding="utf-8")
    (tmp_path / "example.toml").write_text(
        'schema_version=1\nname="bad"\ndescription="bad"\n'
        'variant="SN"\nkeyfile="../outside.key"\n',
        encoding="utf-8",
    )

    with pytest.raises(catalog.CatalogError, match="escapes example directory"):
        catalog.load_example(tmp_path)


def test_load_examples_rejects_duplicate_manifest_names(tmp_path: Path) -> None:
    catalog = import_module("fvs_test.catalog")
    for directory_name in ("one", "two"):
        directory = tmp_path / directory_name
        directory.mkdir()
        (directory / "stand.key").write_text("STOP\n", encoding="utf-8")
        (directory / "example.toml").write_text(
            'schema_version=1\nname="duplicate"\ndescription="duplicate"\n'
            'variant="SN"\nkeyfile="stand.key"\n',
            encoding="utf-8",
        )

    with pytest.raises(catalog.CatalogError, match="duplicate example name"):
        catalog.load_examples(tmp_path)
