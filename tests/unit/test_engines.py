from dataclasses import replace
from pathlib import Path

import pytest

from fvs_test.catalog import load_example
from fvs_test.engines import create_adapter
from fvs_test.engines.base import EngineDefinition, EngineValidationError, RunRequest
from fvs_test.engines.fvsjl import FVSjlAdapter
from fvs_test.engines.native import NativeAdapter
from fvs_test.engines.windows_rfvs import WindowsRFVSAdapter, wsl_to_windows_path


FIXTURE = Path(__file__).parents[1] / "fixtures" / "examples" / "minimal"


def _request(definition: EngineDefinition, workspace: Path) -> RunRequest:
    return RunRequest(
        run_id="test-run",
        engine=definition,
        example=load_example(FIXTURE),
        workspace=workspace,
        timeout_seconds=30.0,
    )


def test_native_adapter_builds_keywordfile_argument(tmp_path: Path) -> None:
    executable = tmp_path / "FVSsn"
    executable.write_text("", encoding="utf-8")
    executable.chmod(0o755)
    definition = EngineDefinition("official-sn", "native", executable, variants=("SN",))
    workspace = tmp_path / "run"
    workspace.mkdir()
    adapter = NativeAdapter(definition)

    command = adapter.command(_request(definition, workspace))

    assert command == (
        str(executable),
        f"--keywordfile={workspace / 'stand.key'}",
    )


def test_native_adapter_preserves_nested_keyword_path(tmp_path: Path) -> None:
    executable = tmp_path / "FVSsn"
    definition = EngineDefinition("official-sn", "native", executable, variants=("SN",))
    workspace = tmp_path / "run"
    example = load_example(FIXTURE)
    request = replace(
        _request(definition, workspace),
        example=replace(example, keyfile=example.root / "controls" / "stand.key"),
    )

    command = NativeAdapter(definition).command(request)

    assert command == (
        str(executable),
        f"--keywordfile={workspace / 'controls' / 'stand.key'}",
    )


def test_fvsjl_adapter_builds_julia_cli_command(tmp_path: Path) -> None:
    julia = tmp_path / "julia"
    julia.write_text("", encoding="utf-8")
    julia.chmod(0o755)
    project = tmp_path / "FVSjl"
    (project / "bin").mkdir(parents=True)
    (project / "bin" / "fvsjl-run.jl").write_text("", encoding="utf-8")
    definition = EngineDefinition(
        "fvsjl",
        "fvsjl",
        julia,
        project=project,
        variants=("SN",),
    )
    workspace = tmp_path / "run"
    workspace.mkdir()
    adapter = FVSjlAdapter(definition)

    command = adapter.command(_request(definition, workspace))

    assert command == (
        str(julia),
        f"--project={project}",
        str(project / "bin" / "fvsjl-run.jl"),
        str(workspace / "stand.key"),
        "--variant=SN",
        "-o",
        str(workspace / "fvsjl.sum"),
    )


def test_probe_explains_missing_executable(tmp_path: Path) -> None:
    definition = EngineDefinition("missing", "native", tmp_path / "missing")

    status = NativeAdapter(definition).probe()

    assert status.available is False
    assert "not executable" in status.diagnostic


def test_native_accepts_fortran_stop_10_but_fvsjl_does_not(tmp_path: Path) -> None:
    executable = tmp_path / "engine"
    definition = EngineDefinition("engine", "native", executable)

    assert NativeAdapter(definition).accepts_exit_code(10) is True
    assert FVSjlAdapter(definition).accepts_exit_code(10) is False


def test_windows_path_conversion_is_pure() -> None:
    assert wsl_to_windows_path(Path("/mnt/c/FVS/My Run/input.db")) == (
        "C:/FVS/My Run/input.db"
    )
    with pytest.raises(ValueError, match="WSL mounted drive"):
        wsl_to_windows_path(Path("/tmp/input.db"))


def test_windows_rfvs_adapter_builds_worker_command() -> None:
    definition = EngineDefinition(
        "windows-rfvs",
        "windows-rfvs",
        Path("/mnt/c/FVS/R/bin/x64/Rscript.exe"),
        fvs_bin=Path("/mnt/c/FVS/FVSbin"),
        variants=("SN",),
    )
    workspace = Path("/mnt/c/FVS/runs/test-run")
    adapter = WindowsRFVSAdapter(definition)

    command = adapter.command(_request(definition, workspace))

    assert command == (
        "/mnt/c/FVS/R/bin/x64/Rscript.exe",
        "--vanilla",
        "C:/FVS/runs/test-run/run_rfvs.R",
        "C:/FVS/runs/test-run/stand.key",
        "C:/FVS/FVSbin",
        "C:/FVS/R/library",
    )


def test_windows_rfvs_adapter_rejects_non_windows_workspace() -> None:
    definition = EngineDefinition(
        "windows-rfvs",
        "windows-rfvs",
        Path("/mnt/c/FVS/R/bin/x64/Rscript.exe"),
        fvs_bin=Path("/mnt/c/FVS/FVSbin"),
        variants=("SN",),
    )

    with pytest.raises(EngineValidationError, match="WSL mounted drive"):
        WindowsRFVSAdapter(definition).command(
            _request(definition, Path("/tmp/fvs-test-run"))
        )


def test_factory_rejects_unknown_adapter(tmp_path: Path) -> None:
    definition = EngineDefinition("bad", "bad", tmp_path / "bad")

    with pytest.raises(ValueError, match="unknown adapter"):
        create_adapter(definition)
