from importlib import import_module
from pathlib import Path

import pytest


def test_local_config_overrides_installation_path(tmp_path: Path) -> None:
    config = import_module("fvs_test.config")
    base = tmp_path / "engines.toml"
    local = tmp_path / "local.toml"
    base.write_text(
        '[engines.native]\nadapter="native"\nexecutable="/opt/FVSsn"\n'
        'variants=["SN"]\n',
        encoding="utf-8",
    )
    local.write_text(
        '[engines.native]\nexecutable="~/bin/FVSsn"\n',
        encoding="utf-8",
    )

    definitions = config.load_engine_definitions(base, local)

    assert definitions["native"].adapter == "native"
    assert definitions["native"].executable == Path.home() / "bin" / "FVSsn"


def test_config_rejects_unknown_adapter(tmp_path: Path) -> None:
    config = import_module("fvs_test.config")
    path = tmp_path / "engines.toml"
    path.write_text(
        '[engines.bad]\nadapter="shell-template"\nexecutable="/bin/false"\n',
        encoding="utf-8",
    )

    with pytest.raises(config.ConfigError, match="unknown adapter"):
        config.load_engine_definitions(path)


def test_local_config_cannot_change_adapter(tmp_path: Path) -> None:
    config = import_module("fvs_test.config")
    base = tmp_path / "engines.toml"
    local = tmp_path / "local.toml"
    base.write_text(
        '[engines.native]\nadapter="native"\nexecutable="/opt/FVSsn"\n',
        encoding="utf-8",
    )
    local.write_text(
        '[engines.native]\nadapter="fvsjl"\n',
        encoding="utf-8",
    )

    with pytest.raises(config.ConfigError, match="may not override adapter"):
        config.load_engine_definitions(base, local)
