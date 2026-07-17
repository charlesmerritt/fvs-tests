# Unified FVS CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a serial `fvs-test` Python CLI that selects a named example and FVS engine, preserves run artifacts, and compares SQLite results against known outputs with DuckDB and declared tolerances.

**Architecture:** Parsed example bundles and engine definitions feed typed adapters behind one `EngineAdapter` protocol. Each adapter runs one subprocess in an isolated workspace and returns a serializable `RunResult`; a separate comparator extracts SQLite content with `sqlite3` and uses DuckDB to produce keyed differences. The same plain request/result boundary can later support container-backed adapters without adding container machinery now.

**Tech Stack:** Python 3.12+, `uv`, standard-library `argparse`, immutable dataclasses, `sqlite3`, DuckDB, pytest, Ruff, ty, GNU Make, GitHub Actions.

## Global Constraints

- Run one engine subprocess at a time; do not introduce workers, threads, async scheduling, or automatic retries.
- Invoke subprocesses with argument vectors and `shell=False`.
- Use explicit timeouts and retain failed-run artifacts.
- Keep FVS installations, credentials, licensed inputs, and machine-local paths out of git.
- Compare SQLite content rather than database file bytes.
- Numeric equality is `abs(actual - expected) <= abs_tol + rel_tol * abs(expected)`; identifiers and categorical values are exact.
- Use `sqlite3` for offline-safe extraction and DuckDB for keyed comparison; do not require DuckDB's downloadable SQLite extension.
- Live engine tests are opt-in and skipped when their configured runtime is unavailable.
- Container, remote, parallel, checkpoint, state-mutation, and deployment work remains out of scope.

---

### Task 1: Bootstrap an installable, checked CLI package

**Files:**
- Create: `.python-version`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `src/fvs_test/__init__.py`
- Create: `src/fvs_test/cli.py`
- Create: `tests/unit/test_cli.py`
- Modify: `docs/superpowers/specs/2026-07-16-unified-fvs-cli-design.md`

**Interfaces:**
- Consumes: approved CLI names `engines`, `examples`, `run`, and `compare`.
- Produces: `fvs_test.cli.build_parser() -> argparse.ArgumentParser` and `fvs_test.cli.main(argv: Sequence[str] | None = None) -> int`.

- [x] **Step 1: Initialize project metadata with the inspected Python template guidance**

Run:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv init --lib --name fvs-test --python 3.12
env UV_CACHE_DIR=/tmp/uv-cache uv add duckdb
env UV_CACHE_DIR=/tmp/uv-cache uv add --dev pytest ruff ty
```

Expected: `pyproject.toml`, `.python-version`, `src/fvs_test/`, and `uv.lock` exist; DuckDB is a runtime dependency and pytest/Ruff/ty are development dependencies.

- [x] **Step 2: Write the failing CLI parser test**

Create `tests/unit/test_cli.py`:

```python
from fvs_test.cli import build_parser


def test_parser_exposes_top_level_commands() -> None:
    parser = build_parser()
    action = next(action for action in parser._actions if action.dest == "command")
    assert set(action.choices) == {"engines", "examples", "run", "compare"}
```

- [x] **Step 3: Run the test to verify it fails**

Run: `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_cli.py -q`

Expected: FAIL because `fvs_test.cli` or `build_parser` does not exist.

- [x] **Step 4: Implement the minimal parser and entrypoint**

Create `src/fvs_test/cli.py`:

```python
from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fvs-test")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("engines", help="list configured FVS engines")
    commands.add_parser("examples", help="list example input bundles")

    run = commands.add_parser("run", help="run one example through one engine")
    run.add_argument("--engine", required=True)
    run.add_argument("--example", required=True)
    run.add_argument("--timeout", type=float, default=120.0)

    compare = commands.add_parser("compare", help="compare an output database")
    compare.add_argument("--example", required=True)
    compare.add_argument("--actual", required=True)
    compare.add_argument("--expected")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Set the project script in `pyproject.toml`:

```toml
[project.scripts]
fvs-test = "fvs_test.cli:main"
```

- [x] **Step 5: Add the smallest project Makefile and ignore generated state**

Create `Makefile`:

```make
.PHONY: install format lint typecheck test check run

ENGINE ?= fvsjl
EXAMPLE ?= thinba

install:
	uv sync --all-groups

format:
	uv run ruff format .

lint:
	uv run ruff check .

typecheck:
	uv run ty check

test:
	uv run pytest

check: lint typecheck test

run:
	uv run fvs-test run --engine $(ENGINE) --example $(EXAMPLE)
```

Create `.gitignore`:

```gitignore
.venv/
.pytest_cache/
.ruff_cache/
.runs/
fvs-test.local.toml
__pycache__/
*.py[cod]
```

- [x] **Step 6: Mark the approved design status and verify the bootstrap**

Change the design status to `approved` and run:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_cli.py -q
env UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
env UV_CACHE_DIR=/tmp/uv-cache uv run ty check
```

Expected: one test passes; Ruff and ty exit zero.

- [x] **Step 7: Commit**

```bash
git add .python-version .gitignore pyproject.toml uv.lock Makefile src/fvs_test tests/unit/test_cli.py docs/superpowers/specs/2026-07-16-unified-fvs-cli-design.md
git commit -m "chore: bootstrap FVS test CLI"
```

### Task 2: Parse safe, versioned example bundles

**Files:**
- Create: `src/fvs_test/models.py`
- Create: `src/fvs_test/catalog.py`
- Create: `tests/unit/test_catalog.py`
- Create: `tests/fixtures/examples/minimal/example.toml`
- Create: `tests/fixtures/examples/minimal/stand.key`
- Create: `tests/fixtures/examples/minimal/stand.tre`

**Interfaces:**
- Consumes: an examples root containing one directory per `example.toml`.
- Produces: `Tolerance`, `TablePolicy`, `ComparisonPolicy`, `Example`; `load_example(path: Path) -> Example`; `load_examples(root: Path) -> dict[str, Example]`.

- [x] **Step 1: Write manifest parser tests first**

Create `tests/unit/test_catalog.py` with tests for a valid bundle, a missing asset, duplicate names, and a path escape:

```python
from pathlib import Path

import pytest

from fvs_test.catalog import CatalogError, load_example, load_examples


FIXTURES = Path(__file__).parents[1] / "fixtures" / "examples"


def test_load_example_resolves_declared_assets() -> None:
    example = load_example(FIXTURES / "minimal")
    assert example.name == "minimal"
    assert example.variant == "SN"
    assert example.keyfile.name == "stand.key"
    assert example.tree_data is not None
    assert example.comparison.tables["summary"].keys == ("case_id", "year")


def test_load_example_rejects_path_escape(tmp_path: Path) -> None:
    (tmp_path / "example.toml").write_text(
        'schema_version=1\nname="bad"\ndescription="bad"\nvariant="SN"\nkeyfile="../outside.key"\n'
    )
    with pytest.raises(CatalogError, match="escapes example directory"):
        load_example(tmp_path)
```

Create the minimal fixture manifest:

```toml
schema_version = 1
name = "minimal"
description = "Synthetic parser fixture"
variant = "SN"
keyfile = "stand.key"
tree_data = "stand.tre"

[comparison]
default_absolute_tolerance = 1.0e-6
default_relative_tolerance = 1.0e-6

[comparison.tables.summary]
keys = ["case_id", "year"]
ignore_columns = ["generated_at"]
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_catalog.py -q`

Expected: collection FAIL because `fvs_test.catalog` does not exist.

- [x] **Step 3: Implement immutable manifest models**

Create `src/fvs_test/models.py` with validated frozen dataclasses:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Tolerance:
    absolute: float = 1.0e-6
    relative: float = 1.0e-6


@dataclass(frozen=True)
class TablePolicy:
    keys: tuple[str, ...]
    ignore_columns: tuple[str, ...] = ()
    tolerances: dict[str, Tolerance] = field(default_factory=dict)


@dataclass(frozen=True)
class ComparisonPolicy:
    default_tolerance: Tolerance
    tables: dict[str, TablePolicy]


@dataclass(frozen=True)
class Example:
    name: str
    description: str
    variant: str
    root: Path
    keyfile: Path
    tree_data: Path | None
    input_db: Path | None
    expected_db: Path | None
    comparison: ComparisonPolicy
```

- [x] **Step 4: Implement TOML parsing and containment checks**

Create `src/fvs_test/catalog.py`. Use `tomllib`, resolve every declared asset,
require `schema_version == 1`, reject empty keys, require files to exist, and
verify `path.is_relative_to(root.resolve())`. `load_examples` must reject duplicate
manifest names and return entries sorted by name.

The public error is:

```python
class CatalogError(ValueError):
    pass
```

- [x] **Step 5: Run focused and project checks**

Run:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_catalog.py -q
env UV_CACHE_DIR=/tmp/uv-cache make check
```

Expected: catalog tests and all project checks pass.

- [x] **Step 6: Commit**

```bash
git add src/fvs_test/models.py src/fvs_test/catalog.py tests/unit/test_catalog.py tests/fixtures/examples/minimal
git commit -m "feat: add example bundle catalog"
```

### Task 3: Load engine definitions and expose typed adapters

**Files:**
- Create: `config/engines.toml`
- Create: `config/fvs-test.local.example.toml`
- Create: `src/fvs_test/config.py`
- Create: `src/fvs_test/engines/__init__.py`
- Create: `src/fvs_test/engines/base.py`
- Create: `src/fvs_test/engines/native.py`
- Create: `src/fvs_test/engines/fvsjl.py`
- Create: `src/fvs_test/engines/windows_rfvs.py`
- Create: `tests/unit/test_config.py`
- Create: `tests/unit/test_engines.py`

**Interfaces:**
- Consumes: trusted adapter names and installation paths from TOML.
- Produces: `EngineDefinition`, `EngineStatus`, `RunRequest`, `EngineAdapter`; `load_engine_definitions(base, local=None)`; `create_adapter(definition)`.

- [x] **Step 1: Write failing engine configuration and adapter tests**

Tests must prove that local TOML overrides only named path/version fields, unknown
adapter names fail, unavailable executables produce useful probe diagnostics, and
the native/FVSjl adapters build exact argument vectors.

Representative assertions:

```python
assert native.command(request) == (
    str(executable),
    f"--keywordfile={request.workspace / 'stand.key'}",
)
assert fvsjl.command(request) == (
    str(julia),
    f"--project={project}",
    str(project / "bin" / "fvsjl-run.jl"),
    str(request.workspace / "stand.key"),
    "--variant=SN",
)
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_config.py tests/unit/test_engines.py -q`

Expected: collection FAIL because the engine modules do not exist.

- [x] **Step 3: Implement engine data contracts and protocol**

In `engines/base.py`, define frozen dataclasses and the protocol:

```python
@dataclass(frozen=True)
class EngineDefinition:
    name: str
    adapter: str
    executable: Path
    project: Path | None = None
    fvs_bin: Path | None = None
    variants: tuple[str, ...] = ()


@dataclass(frozen=True)
class EngineStatus:
    name: str
    available: bool
    version: str | None
    diagnostic: str


@dataclass(frozen=True)
class RunRequest:
    run_id: str
    engine: EngineDefinition
    example: Example
    workspace: Path
    timeout_seconds: float


class EngineAdapter(Protocol):
    @property
    def definition(self) -> EngineDefinition: ...
    def probe(self) -> EngineStatus: ...
    def validate(self, example: Example) -> None: ...
    def command(self, request: RunRequest) -> tuple[str, ...]: ...
    def discover_outputs(self, workspace: Path) -> tuple[Path, ...]: ...
```

Task 4 extends the protocol and concrete adapters with `run` after `RunResult`
exists. Command construction and artifact discovery remain adapter-specific;
subprocess mechanics remain centralized.

- [x] **Step 4: Implement trusted engine config parsing**

`load_engine_definitions` parses `[engines.<name>]`, expands `~`, merges an optional
ignored local file by engine name, and accepts only `native`, `fvsjl`, and
`windows-rfvs` adapter values. Configuration contains paths and variants, never a
shell command or free-form arguments.

The committed `config/engines.toml` defines conventional local installations:

```toml
[engines.fvsjl]
adapter = "fvsjl"
executable = "~/.juliaup/bin/julia"
project = "~/projects/FVSjl"
variants = ["SN", "NE"]

[engines.official-sn]
adapter = "native"
executable = "~/projects/ForestVegetationSimulator/bin/FVSsn"
variants = ["SN"]

[engines.fvs-modern-sn]
adapter = "native"
executable = "~/projects/fvs-modern/lib/FVSsn"
variants = ["SN"]

[engines.windows-rfvs]
adapter = "windows-rfvs"
executable = "/mnt/c/FVS/FVSSoftware/R/R-4.5.0/bin/x64/Rscript.exe"
fvs_bin = "/mnt/c/FVS/FVSSoftware/FVSbin"
variants = ["SN"]
```

- [x] **Step 5: Implement adapter probes, validation, commands, and discovery**

- Native validates the variant and keyfile, invokes `<executable>
  --keywordfile=<workspace-keyfile>`, and discovers new regular files excluding
  copied inputs and logs.
- FVSjl validates the project CLI exists and the example has `.key` or `.yaml`,
  invokes Julia with `--project`, the CLI script, input, and variant.
- Windows rFVS initially probes `Rscript.exe` and `fvs_bin`; its `command` raises
  a precise unsupported-live-run error until the tested R wrapper is added in
  Task 7. Path conversion is a pure `wsl_to_windows_path(Path) -> str` function.

- [x] **Step 6: Verify and commit**

Run: `env UV_CACHE_DIR=/tmp/uv-cache make check`

Expected: all tests and static checks pass.

```bash
git add config src/fvs_test/config.py src/fvs_test/engines tests/unit/test_config.py tests/unit/test_engines.py
git commit -m "feat: add typed FVS engine adapters"
```

### Task 4: Run one engine safely in an isolated workspace

**Files:**
- Create: `src/fvs_test/workspace.py`
- Create: `src/fvs_test/runner.py`
- Modify: `src/fvs_test/engines/native.py`
- Modify: `src/fvs_test/engines/fvsjl.py`
- Modify: `src/fvs_test/engines/windows_rfvs.py`
- Create: `tests/unit/test_workspace.py`
- Create: `tests/unit/test_runner.py`
- Modify: `tests/unit/test_engines.py`

**Interfaces:**
- Consumes: `Example`, `RunRequest`, and `EngineAdapter` from prior tasks.
- Produces: `create_workspace(runs_root, run_id, example) -> Path`; internal `run_engine(adapter, request) -> RunResult`; public `EngineAdapter.run(request) -> RunResult`; `write_run_record(result) -> Path`.

- [x] **Step 1: Write failing workspace and runner tests**

Cover copied inputs, source containment, success, nonzero exit, timeout, output
discovery, logs, single-thread environment defaults, and `run.json` on every
outcome. Inject a callable process runner so unit tests do not launch FVS.

The success test must assert:

```python
assert result.status == RunStatus.SUCCESS
assert result.command == adapter.command(request)
assert result.stdout_path.read_text() == "engine output\n"
assert result.stderr_path.read_text() == ""
assert result.record_path.exists()
```

- [x] **Step 2: Run tests and observe the expected failure**

Run: `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_workspace.py tests/unit/test_runner.py -q`

Expected: collection FAIL for missing modules.

- [x] **Step 3: Implement workspace copying**

`create_workspace` creates `<runs_root>/<run_id>/`, rejects an existing path, and
copies only manifest-declared inputs while preserving their relative names. It
does not copy `expected_db` into the engine workspace. Return the resolved
workspace path.

- [x] **Step 4: Implement process execution and durable results**

Add to `engines/base.py`:

```python
class RunStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class RunResult:
    run_id: str
    engine: str
    adapter: str
    variant: str
    status: RunStatus
    command: tuple[str, ...]
    workspace: Path
    started_at: str
    elapsed_seconds: float
    exit_code: int | None
    stdout_path: Path
    stderr_path: Path
    artifacts: tuple[Path, ...]
    diagnostic: str | None
    record_path: Path
```

`run_engine` uses `subprocess.run(..., shell=False, cwd=request.workspace,
capture_output=True, text=True, timeout=..., check=False)` and sets
`JULIA_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, and `OMP_NUM_THREADS=1` only when
not already provided. Catch `TimeoutExpired`, write partial output, and always
serialize `run.json` with paths relative to the workspace where possible.

Each concrete adapter implements the approved protocol by delegating to the
shared runner:

```python
def run(self, request: RunRequest) -> RunResult:
    from fvs_test.runner import run_engine

    return run_engine(self, request)
```

`Application` and other consumers call `adapter.run(request)`; only runner unit
tests call `run_engine` directly to inject deterministic subprocess results.

- [x] **Step 5: Verify and commit**

Run: `env UV_CACHE_DIR=/tmp/uv-cache make check`

Expected: runner tests and all checks pass.

```bash
git add src/fvs_test/workspace.py src/fvs_test/runner.py src/fvs_test/engines tests/unit/test_workspace.py tests/unit/test_runner.py tests/unit/test_engines.py
git commit -m "feat: add isolated serial engine runs"
```

### Task 5: Compare SQLite outputs with DuckDB

**Files:**
- Create: `src/fvs_test/comparison.py`
- Create: `tests/unit/test_comparison.py`

**Interfaces:**
- Consumes: actual/expected SQLite paths and `ComparisonPolicy`.
- Produces: `Difference`, `ComparisonResult`, `compare_databases(actual, expected, policy) -> ComparisonResult`, and `write_comparison(result, path) -> Path`.

- [x] **Step 1: Write failing comparison tests with generated SQLite databases**

Use `sqlite3` in fixtures to create small `summary(case_id, year, volume,
label, generated_at)` tables. Cover exact equality, within/outside tolerance,
missing tables, missing/extra rows, schema drift, nulls, ignored columns, and
duplicate keys.

Representative tolerance test:

```python
result = compare_databases(actual, expected, policy)
assert result.equivalent is True
assert result.differences == ()
```

The outside-tolerance test asserts a `Difference(kind="value", table="summary",
column="volume", ...)` with absolute and relative values.

- [x] **Step 2: Run tests to verify failure**

Run: `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_comparison.py -q`

Expected: collection FAIL because `fvs_test.comparison` does not exist.

- [x] **Step 3: Implement read-only SQLite extraction**

Open SQLite with `sqlite3.connect(f"file:{path}?mode=ro", uri=True)`. For each
declared table, quote identifiers only after verifying them against the schema,
validate key columns, reject duplicate keys, and normalize rows to cell records:

```python
@dataclass(frozen=True)
class Cell:
    source: str
    table_name: str
    row_key: str
    column_name: str
    value_kind: str
    text_value: str | None
    numeric_value: float | None
```

Use compact sorted JSON for `row_key` so composite keys are stable.

- [x] **Step 4: Implement DuckDB full-outer comparison**

Create an in-memory DuckDB connection, create a typed `cells` table, insert
expected and actual cells with `executemany`, and run a full outer join on table,
row key, and column. Apply exact comparison to nonnumeric kinds and the declared
tolerance formula to numeric values. Add schema/table/row differences before cell
comparison so diagnostics remain explicit.

Return:

```python
@dataclass(frozen=True)
class ComparisonResult:
    equivalent: bool
    actual: Path
    expected: Path
    differences: tuple[Difference, ...]

    def counts(self) -> dict[str, int]: ...
```

- [x] **Step 5: Serialize and verify**

`write_comparison` writes `comparison.json` with database paths, equivalence,
counts, and all differences. Run:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_comparison.py -q
env UV_CACHE_DIR=/tmp/uv-cache make check
```

Expected: all comparison cases and project checks pass without downloading a
DuckDB extension.

- [x] **Step 6: Commit**

```bash
git add src/fvs_test/comparison.py tests/unit/test_comparison.py
git commit -m "feat: compare FVS SQLite outputs"
```

### Task 6: Wire catalogs, adapters, runs, and comparison into the CLI

**Files:**
- Create: `src/fvs_test/application.py`
- Modify: `src/fvs_test/cli.py`
- Modify: `tests/unit/test_cli.py`
- Create: `tests/integration/test_cli_run.py`

**Interfaces:**
- Consumes: catalogs, adapter factory, runner, and comparator.
- Produces: `Application.list_engines()`, `Application.list_examples()`, `Application.run(engine_name, example_name, timeout)`, `Application.compare(example_name, actual, expected=None)`; fully functional `fvs-test` commands.

- [x] **Step 1: Write CLI behavior tests before orchestration code**

Unit tests inject a fake `Application` and assert output/exit codes for available
and unavailable engines, example listing, passing runs, failed runs, and comparison
mismatches. The integration test creates a temporary executable fake native engine
with a shebang, writes an output SQLite DB, configures it through temporary TOML,
and invokes `python -m fvs_test.cli run ...` in a subprocess.

- [x] **Step 2: Run tests and observe failure**

Run: `env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_cli.py tests/integration/test_cli_run.py -q`

Expected: FAIL because `Application` and command dispatch are absent.

- [x] **Step 3: Implement application orchestration**

`Application.from_paths(repo_root, engine_config, local_config, runs_root)` loads
catalogs once. `run` creates a UTC timestamp/UUID run ID, probes and validates the
adapter, creates the workspace, executes, finds the first produced `.db`, and
compares it when the example has `expected_db`. Write `comparison.json` into the
workspace and return both result objects.

No database output is not an error for examples without a known database. It is
an explicit failure when a baseline exists.

- [x] **Step 4: Implement command dispatch and readable output**

Add global testable path flags:

```text
--repo-root PATH
--engine-config PATH
--local-config PATH
--runs-root PATH
```

Defaults are the repository root discovered from `__file__`,
`config/engines.toml`, optional `fvs-test.local.toml`, and `.runs/`. Print one
engine/example per line, print the retained workspace for every run, show
comparison counts plus at most 20 differences, and return 1 for execution failure
or mismatch.

- [x] **Step 5: Verify and commit**

Run:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_cli.py tests/integration/test_cli_run.py -q
env UV_CACHE_DIR=/tmp/uv-cache make check
```

Expected: end-to-end fake engine run and all checks pass.

```bash
git add src/fvs_test/application.py src/fvs_test/cli.py tests/unit/test_cli.py tests/integration/test_cli_run.py
git commit -m "feat: wire unified FVS CLI workflow"
```

### Task 7: Add a provenance-safe example and qualify local adapters

**Files:**
- Create: `examples/thinba/example.toml`
- Create: `examples/thinba/README.md`
- Create: `examples/thinba/thinba.key`
- Create: `examples/thinba/thinba.tre`
- Create: `tests/integration/test_live_engines.py`
- Modify: `src/fvs_test/engines/windows_rfvs.py`
- Create: `src/fvs_test/engines/run_rfvs.R`

**Interfaces:**
- Consumes: FVSjl and official/native installations configured in Task 3.
- Produces: a distributable file-backed `thinba` example and opt-in serial live smoke tests; a concrete Windows rFVS subprocess command when its runtime is present.

- [x] **Step 1: Copy and document the reviewed thinba input pair**

Copy only `thinba.key` and `thinba.tre` from
`~/projects/FVSjl/examples/legacy/`.
Record source repository, source commit, Southern variant, redistribution basis,
and the exact regeneration/copy command in `examples/thinba/README.md`. The
manifest has no expected database until a provenance-safe database baseline is
reviewed; it still exercises artifact capture for summary output.

- [x] **Step 2: Write opt-in live tests before adapter qualification**

Use markers `live_engine` and environment/config availability checks. Each test
runs one engine, once, with a 120-second timeout and asserts success, retained
logs, and at least one scientific output artifact. Never run these tests in
parallel or retry a failure.

- [x] **Step 3: Run catalog tests and one local FVSjl smoke**

Run:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/unit/test_catalog.py -q
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/integration/test_live_engines.py -m live_engine -k fvsjl -q
```

Expected: catalog PASS; FVSjl PASS or one explicit failure preserved under
`.runs/`. If FVSjl fails, stop live engine execution, document the diagnostic,
and do not auto-retry.

- [x] **Step 4: Qualify official native execution only if FVSjl remained stable**

Run one native smoke:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/integration/test_live_engines.py -m live_engine -k official -q
```

Expected: PASS with retained output, or a documented adapter/runtime gap. Do not
run the full external FVS suites.

- [x] **Step 5: Implement the Windows rFVS wrapper and unit-test its command**

The R wrapper accepts keyfile, FVS binary directory, and R library directory
arguments, loads rFVS, runs one keyfile, and exits nonzero on failure.
The Python adapter converts workspace paths with `wslpath -w` semantics without
shell interpolation and launches one Windows `Rscript.exe` process. Unit tests
mock path conversion and subprocess execution. Live execution remains skipped
when Windows paths are absent.

- [x] **Step 6: Verify non-live checks and commit**

Run: `env UV_CACHE_DIR=/tmp/uv-cache make check`

Expected: all deterministic checks pass; report live evidence separately.

```bash
git add examples/thinba src/fvs_test/engines/windows_rfvs.py src/fvs_test/engines/run_rfvs.R tests/integration/test_live_engines.py pyproject.toml
git commit -m "feat: add real FVS smoke adapters"
```

### Task 8: Finish CI, docs, and agent-operable handoff

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `notes/README.md`
- Modify: `tests/fixtures/README.md`
- Modify: `tests/interfaces/README.md`
- Modify: `templates/interface/README.md`

**Interfaces:**
- Consumes: complete CLI and Make targets.
- Produces: one documented setup/run/test path, deterministic GitHub CI, and a clear legacy-scaffold migration note.

- [ ] **Step 1: Add CI that runs only deterministic checks**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.12"
          enable-cache: true
      - run: uv sync --locked --all-groups
      - run: make check
```

- [ ] **Step 2: Rewrite README around the executable workflow**

Document prerequisites, `uv sync`, local engine paths, `fvs-test engines`,
`examples`, `run`, and `compare`; explain `.runs/<run-id>/`; show how to add an
adapter and example; explain that CI uses fake engines and that live tests are
opt-in. State that continuous deployment is not applicable because there is no
service or package publication target.

- [ ] **Step 3: Update durable notes and the initial placeholder scaffold**

Record implemented engine status, live smoke evidence, the database-baseline
gap, and the container-orchestration future. Update the old interface template
READMEs to point to the typed-adapter and example-bundle docs rather than
presenting the original directory-per-interface structure as current.

- [ ] **Step 4: Run final verification from documented commands**

Run:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv sync --locked --all-groups
env UV_CACHE_DIR=/tmp/uv-cache make check
env UV_CACHE_DIR=/tmp/uv-cache uv run fvs-test engines
env UV_CACHE_DIR=/tmp/uv-cache uv run fvs-test examples
```

Expected: sync and checks exit zero; CLI lists configured engines and `thinba`.

- [ ] **Step 5: Inspect change scope and commit**

Run: `git diff --check && git status --short`

Expected: only plan-scoped project files are modified.

```bash
git add .github/workflows/ci.yml README.md notes/README.md tests/fixtures/README.md tests/interfaces/README.md templates/interface/README.md
git commit -m "docs: document unified FVS workflow"
```

- [ ] **Step 6: Record final milestone evidence**

Update the plan checkboxes, notes, and final response with exact deterministic
test counts, live-engine outcomes, commit hashes, and remaining gaps. Do not claim
a live adapter works unless its smoke command ran successfully in this session.

## Plan completion criteria

- `make check` passes from a clean checkout after `uv sync --locked --all-groups`.
- `fvs-test engines` and `fvs-test examples` return useful current state.
- A fake native engine completes the entire run, artifact, and database comparison path in CI.
- At least one real local engine is attempted serially with a timeout; its pass or retained failure is documented.
- The visual architecture review, approved design, this plan, README, and notes agree on Architecture A now and container-backed Architecture C later.
- No unknown-provenance SQLite database, external engine installation, generated run workspace, or credential is tracked.
