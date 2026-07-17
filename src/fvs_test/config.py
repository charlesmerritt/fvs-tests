from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, cast

from fvs_test.engines.base import EngineDefinition


KNOWN_ADAPTERS = frozenset({"native", "fvsjl", "windows-rfvs"})
LOCAL_OVERRIDE_KEYS = frozenset({"executable", "project", "fvs_bin", "variants"})


class ConfigError(ValueError):
    pass


def load_engine_definitions(
    path: Path,
    local_path: Path | None = None,
) -> dict[str, EngineDefinition]:
    base = _engine_tables(path)
    if local_path is not None and local_path.is_file():
        for name, overrides in _engine_tables(local_path).items():
            if name not in base:
                raise ConfigError(f"local config references unknown engine: {name}")
            if "adapter" in overrides:
                raise ConfigError("local config may not override adapter")
            unknown = set(overrides).difference(LOCAL_OVERRIDE_KEYS)
            if unknown:
                raise ConfigError(f"unknown local engine fields: {sorted(unknown)}")
            base[name] = {**base[name], **overrides}
    return {name: _definition(name, values) for name, values in sorted(base.items())}


def _engine_tables(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("rb") as stream:
        document = tomllib.load(stream)
    engines = document.get("engines")
    if not isinstance(engines, dict):
        raise ConfigError("config must contain an engines table")
    result: dict[str, dict[str, Any]] = {}
    for name, values in engines.items():
        if not isinstance(name, str) or not isinstance(values, dict):
            raise ConfigError("engine names and definitions must be TOML tables")
        result[name] = cast(dict[str, Any], values)
    return result


def _definition(name: str, values: dict[str, Any]) -> EngineDefinition:
    adapter = _string(values, "adapter")
    if adapter not in KNOWN_ADAPTERS:
        raise ConfigError(f"unknown adapter: {adapter}")
    variants = values.get("variants", [])
    if not isinstance(variants, list) or any(
        not isinstance(item, str) for item in variants
    ):
        raise ConfigError(f"engine {name} variants must be a list of strings")
    return EngineDefinition(
        name=name,
        adapter=adapter,
        executable=_path(values, "executable"),
        project=_optional_path(values, "project"),
        fvs_bin=_optional_path(values, "fvs_bin"),
        variants=tuple(item.upper() for item in variants if isinstance(item, str)),
    )


def _string(values: dict[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"engine {key} must be a non-empty string")
    return value


def _path(values: dict[str, Any], key: str) -> Path:
    return Path(_string(values, key)).expanduser()


def _optional_path(values: dict[str, Any], key: str) -> Path | None:
    if key not in values:
        return None
    return _path(values, key)
