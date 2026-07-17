from __future__ import annotations

from fvs_test.engines.base import EngineAdapter, EngineDefinition
from fvs_test.engines.fvsjl import FVSjlAdapter
from fvs_test.engines.native import NativeAdapter
from fvs_test.engines.windows_rfvs import WindowsRFVSAdapter


def create_adapter(definition: EngineDefinition) -> EngineAdapter:
    if definition.adapter == "native":
        return NativeAdapter(definition)
    if definition.adapter == "fvsjl":
        return FVSjlAdapter(definition)
    if definition.adapter == "windows-rfvs":
        return WindowsRFVSAdapter(definition)
    raise ValueError(f"unknown adapter: {definition.adapter}")


__all__ = ["create_adapter"]
