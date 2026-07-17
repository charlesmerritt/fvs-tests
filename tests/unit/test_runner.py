from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import cast

from fvs_test.catalog import load_example
from fvs_test.engines.base import EngineDefinition, RunRequest


FIXTURE = Path(__file__).parents[1] / "fixtures" / "examples" / "minimal"


@dataclass(frozen=True)
class StubAdapter:
    definition: EngineDefinition
    accepted_codes: tuple[int, ...] = (0,)

    def command(self, request: RunRequest) -> tuple[str, ...]:
        return (str(self.definition.executable), "--fake")

    def discover_outputs(self, workspace: Path) -> tuple[Path, ...]:
        output = workspace / "output.db"
        return (output,) if output.is_file() else ()

    def accepts_exit_code(self, exit_code: int) -> bool:
        return exit_code in self.accepted_codes


def _request(tmp_path: Path) -> tuple[StubAdapter, RunRequest]:
    executable = tmp_path / "engine"
    executable.write_text("", encoding="utf-8")
    definition = EngineDefinition("fake", "native", executable, variants=("SN",))
    workspace = tmp_path / "run"
    workspace.mkdir()
    request = RunRequest(
        "run-1",
        definition,
        load_example(FIXTURE),
        workspace,
        15.0,
    )
    return StubAdapter(definition), request


def test_success_writes_logs_metadata_and_artifacts(tmp_path: Path) -> None:
    runner = import_module("fvs_test.runner")
    adapter, request = _request(tmp_path)
    captured: dict[str, object] = {}

    def process(
        command: tuple[str, ...], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        (request.workspace / "output.db").write_bytes(b"sqlite output")
        return subprocess.CompletedProcess(command, 0, "engine output\n", "")

    result = runner.run_engine(adapter, request, process_runner=process)

    assert result.status == runner.RunStatus.SUCCESS
    assert result.command == adapter.command(request)
    assert result.stdout_path.read_text() == "engine output\n"
    assert result.stderr_path.read_text() == ""
    assert result.artifacts == (request.workspace / "output.db",)
    assert captured["shell"] is False
    assert captured["timeout"] == 15.0
    environment = captured["env"]
    assert isinstance(environment, dict)
    environment = cast(dict[str, str], environment)
    assert environment["JULIA_NUM_THREADS"] == "1"
    assert environment["OPENBLAS_NUM_THREADS"] == "1"
    assert environment["OMP_NUM_THREADS"] == "1"
    record = json.loads(result.record_path.read_text())
    assert record["status"] == "success"
    assert record["artifacts"] == ["output.db"]


def test_nonzero_exit_retains_failure_record(tmp_path: Path) -> None:
    runner = import_module("fvs_test.runner")
    adapter, request = _request(tmp_path)

    def process(
        command: tuple[str, ...], **_: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 7, "", "engine failed\n")

    result = runner.run_engine(adapter, request, process_runner=process)

    assert result.status == runner.RunStatus.FAILED
    assert result.exit_code == 7
    assert result.stderr_path.read_text() == "engine failed\n"
    assert result.diagnostic is not None
    assert "code 7" in result.diagnostic
    assert result.record_path.exists()


def test_timeout_retains_partial_output_and_record(tmp_path: Path) -> None:
    runner = import_module("fvs_test.runner")
    adapter, request = _request(tmp_path)

    def process(
        command: tuple[str, ...], **_: object
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            command, 15.0, output="partial\n", stderr="hung\n"
        )

    result = runner.run_engine(adapter, request, process_runner=process)

    assert result.status == runner.RunStatus.TIMED_OUT
    assert result.exit_code is None
    assert result.stdout_path.read_text() == "partial\n"
    assert result.stderr_path.read_text() == "hung\n"
    assert result.diagnostic is not None
    assert "timed out" in result.diagnostic
    assert result.record_path.exists()
