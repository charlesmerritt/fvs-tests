from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any

from fvs_test.engines.base import (
    EngineCommand,
    RunRequest,
    RunResult,
    RunStatus,
)


ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]
THREAD_LIMITS = {
    "JULIA_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
}


def run_engine(
    adapter: EngineCommand,
    request: RunRequest,
    *,
    process_runner: ProcessRunner = subprocess.run,
) -> RunResult:
    command = adapter.command(request)
    stdout_path = request.workspace / "stdout.log"
    stderr_path = request.workspace / "stderr.log"
    record_path = request.workspace / "run.json"
    environment = os.environ.copy()
    for name, value in THREAD_LIMITS.items():
        environment.setdefault(name, value)

    started_at = datetime.now(UTC).isoformat()
    started = monotonic()
    try:
        completed = process_runner(
            command,
            cwd=request.workspace,
            capture_output=True,
            text=True,
            timeout=request.timeout_seconds,
            check=False,
            shell=False,
            env=environment,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        exit_code = completed.returncode
        status = (
            RunStatus.SUCCESS
            if adapter.accepts_exit_code(exit_code)
            else RunStatus.FAILED
        )
        diagnostic = (
            None
            if status is RunStatus.SUCCESS
            else f"engine exited with code {exit_code}"
        )
    except subprocess.TimeoutExpired as error:
        stdout = _text(error.stdout)
        stderr = _text(error.stderr)
        exit_code = None
        status = RunStatus.TIMED_OUT
        diagnostic = f"engine timed out after {request.timeout_seconds:g} seconds"

    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    artifacts = adapter.discover_outputs(request.workspace)
    result = RunResult(
        run_id=request.run_id,
        engine=request.engine.name,
        adapter=request.engine.adapter,
        variant=request.example.variant,
        status=status,
        command=command,
        workspace=request.workspace,
        started_at=started_at,
        elapsed_seconds=monotonic() - started,
        exit_code=exit_code,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        artifacts=artifacts,
        diagnostic=diagnostic,
        record_path=record_path,
    )
    write_run_record(result)
    return result


def write_run_record(result: RunResult) -> Path:
    workspace = result.workspace
    payload: dict[str, Any] = {
        "run_id": result.run_id,
        "engine": result.engine,
        "adapter": result.adapter,
        "variant": result.variant,
        "status": result.status.value,
        "command": list(result.command),
        "workspace": str(workspace),
        "started_at": result.started_at,
        "elapsed_seconds": result.elapsed_seconds,
        "exit_code": result.exit_code,
        "stdout": _relative(result.stdout_path, workspace),
        "stderr": _relative(result.stderr_path, workspace),
        "artifacts": [_relative(path, workspace) for path in result.artifacts],
        "diagnostic": result.diagnostic,
    }
    result.record_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result.record_path


def _relative(path: Path, workspace: Path) -> str:
    try:
        return str(path.relative_to(workspace))
    except ValueError:
        return str(path)


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
