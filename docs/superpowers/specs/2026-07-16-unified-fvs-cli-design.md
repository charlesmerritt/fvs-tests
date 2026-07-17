# Unified FVS CLI Design

- Date: 2026-07-16
- Status: approved
- Architecture review: [`../../architecture/fvs-cli-architecture-review.html`](../../architecture/fvs-cli-architecture-review.html)

## Goal

Build a scalable Python CLI that runs a named example through a selected Forest
Vegetation Simulator (FVS) engine and shows what that engine produced. When the
example declares a known output database, the same workflow compares the actual
SQLite output with that baseline using explicit scientific tolerances.

The primary workflow is:

```console
$ fvs-test run --engine fvsjl --example thinba
```

The first milestone proves serial execution and cross-engine observability. It
does not implement parallel scheduling, iterative checkpoints, or state mutation.

## Success criteria

1. `fvs-test engines` reports configured engines, availability, version when
   discoverable, and a useful diagnostic when unavailable.
2. `fvs-test examples` lists reproducible example bundles and their supported
   inputs, variants, and known baselines.
3. `fvs-test run --engine <name> --example <name>` executes one engine in an
   isolated workspace without invoking a shell.
4. Every run preserves its command, environment metadata, stdout, stderr, exit
   status, duration, copied inputs, and discovered output artifacts.
5. A run with a declared known output database performs a table-aware comparison
   and prints a concise pass/fail summary with actionable differences.
6. Numeric comparison uses per-example absolute and relative tolerances; keys and
   categorical values remain exact.
7. Unit and integration tests exercise the complete CLI path with fake engines
   and small SQLite fixtures in CI. Live FVS tests are opt-in and machine-local.
8. Project setup, commands, fixture provenance, and engine configuration are
   documented and available through a small Makefile.

## Non-goals for the first milestone

- Parallel or distributed engine execution.
- Containers, services, queues, or a remote worker protocol.
- Checkpoint/restart orchestration or Python mutation of FVS state.
- A common in-process API for Julia, Fortran, and R runtimes.
- Performance benchmarking beyond recording elapsed wall time.
- Packaging or publishing FVS binaries, licensed inputs, or machine credentials.
- Replacing engine-specific regression suites.

## Design decision

Use typed Python engine adapters behind one stable run contract (Architecture A
in the review). A configuration-only command-template system was rejected because
Windows path conversion, runtime probing, accepted FVS stop codes, and artifact
discovery would turn configuration into a brittle programming language.

Container or service execution (Architecture C) is the intended long-term route
to many isolated engine instances. It is deferred until the local CLI and run
contract are proven. The initial adapter boundary accepts and returns plain,
serializable data so a later container-backed adapter can preserve the same core
workflow without adding an executor abstraction now.

## Project shape

```text
.
├── examples/
│   └── <example-name>/
│       ├── example.toml
│       ├── inputs...
│       └── expected/
│           └── <known-output>.db
├── src/fvs_test/
│   ├── cli.py
│   ├── catalog.py
│   ├── models.py
│   ├── runner.py
│   ├── workspace.py
│   ├── comparison.py
│   └── engines/
│       ├── base.py
│       ├── fvsjl.py
│       ├── native.py
│       └── windows_rfvs.py
├── tests/
│   ├── fixtures/
│   ├── integration/
│   └── unit/
├── docs/
├── notes/
├── Makefile
├── pyproject.toml
└── uv.lock
```

This is a target shape, not a requirement to create empty modules. Files should
only be added as behavior requires them.

## Core model

### Example bundle

An example is a directory containing `example.toml` and the input assets needed
by one or more engines. Supported asset roles are:

- keyword file (`.key` or engine-supported structured equivalent);
- tree data (`.tre`, `.csv`, or another declared companion);
- SQLite inventory database (`input.db`), when the keyfile uses database input;
- auxiliary files explicitly named by the manifest;
- one or more known output databases under `expected/`.

The manifest declares a stable name, description, FVS variant, asset paths,
redistribution/provenance notes, known baseline, and comparison policy. Paths are
relative to the example directory and may not escape it.

The bundle describes data, not commands. An adapter decides whether it supports
the available assets. This prevents example manifests from accumulating shell
syntax or engine-specific path logic.

Conceptual manifest:

```toml
schema_version = 1
name = "thinba"
description = "Southern variant thinning from below"
variant = "SN"
keyfile = "thinba.key"
tree_data = "thinba.tre"
expected_db = "expected/FVSOut.db"

[comparison]
tables = ["FVS_Cases", "FVS_Summary2", "FVS_Error"]
default_absolute_tolerance = 1.0e-6
default_relative_tolerance = 1.0e-6

[comparison.table.FVS_Summary2]
keys = ["CaseID", "Year", "MgmtID"]
ignore_columns = []

[comparison.table.FVS_Cases]
keys = ["CaseID"]
ignore_columns = ["Version"]
```

The implemented schema may use a less repetitive TOML representation, but it
must preserve these semantics and receive parser tests before fixtures depend on
it.

### Engine adapter

Each engine implements a small protocol:

```python
class EngineAdapter(Protocol):
    name: str

    def probe(self) -> EngineStatus: ...
    def validate(self, example: Example) -> None: ...
    def run(self, request: RunRequest) -> RunResult: ...
```

- `probe` never mutates the engine installation. It reports availability,
  version when practical, supported variants, and diagnostics.
- `validate` fails before execution when required inputs, variants, or output
  capabilities are unsupported.
- `run` builds an argument vector, invokes the engine in the supplied isolated
  workspace, and returns structured results and artifact paths.

Adapters own only engine-specific behavior: command construction, path
translation, accepted return-code interpretation, version probing, and artifact
discovery. They do not compare scientific results or choose tolerances.

Initial adapters:

1. `fvsjl`: invokes the Julia CLI in `~/projects/FVSjl` with a keyfile or YAML
   input and its companion tree data.
2. `native`: invokes an official USDA FVS or `fvs-modern` standalone executable
   using `--keywordfile=<path>`. Executable path and variant are configuration.
3. `windows-rfvs`: specifies the Windows `Rscript.exe`/rFVS route through WSL.
   Its unit-tested path handling and probe belong in the first architecture, but
   live qualification may remain a later opt-in integration task if the host is
   unavailable.

Official FVS and `fvs-modern` share the native executable contract, so they use
separate configured engine records backed by the same adapter implementation.
They remain distinct engine identities in run metadata.

### Engine configuration

The repository contains non-secret example configuration. Local executable and
project paths are read from an ignored local TOML file and may be overridden by
environment variables or CLI options when a test needs it. Built-in detection
may probe conventional locations relative to `Path.home()` and the WSL mount,
but a detected path is reported rather than silently assumed valid.

Configuration selects installations; it does not define arbitrary shell
commands. Argument vectors are always constructed by trusted adapter code.

### Run request and result

`RunRequest` contains only the selected engine identity, parsed example,
workspace path, timeout, and invocation-specific options allowed by that adapter.

`RunResult` records:

- run identifier and timestamps;
- engine name, adapter, detected version, and variant;
- exact argument vector and working directory;
- exit status and normalized success/failure status;
- elapsed wall time;
- stdout and stderr log paths;
- input and output artifact paths with hashes where useful;
- warnings and failure diagnostic;
- optional comparison result.

Both are immutable dataclasses with path validation at system boundaries. They
must not contain live engine handles, database connections, or language-specific
state.

## Execution flow

1. The CLI resolves an engine and example from their catalogs.
2. The adapter is probed and validates the example.
3. The workspace service creates a unique run directory under `.runs/` (ignored
   by git) and copies the example inputs into it.
4. The adapter builds an argument vector using workspace-local paths.
5. The runner executes one subprocess with `shell=False`, an explicit timeout,
   captured stdout/stderr, and conservative single-worker environment defaults.
6. The adapter interprets the process result and discovers artifacts.
7. The runner writes `run.json` even when the engine fails or times out.
8. If the run succeeded and the example declares a baseline, the comparison
   service compares output databases and writes `comparison.json` plus a terminal
   summary.
9. The CLI exits zero only when execution succeeded and any requested comparison
   passed.

Runs are never performed in the source example directory. Failed workspaces are
retained by default because their artifacts are diagnostic evidence.

## SQLite and DuckDB comparison

Comparison is content-aware; SQLite files are never compared byte-for-byte.

The standard-library `sqlite3` module performs reliable, read-only schema and row
extraction. Extracted cells are normalized into DuckDB long-form relations with
source, table, row key, column, type, and value fields. DuckDB performs keyed
full-outer comparisons and produces difference relations. This approach makes
DuckDB a real project dependency without relying on the downloadable DuckDB
SQLite extension in offline CI.

For each declared table, comparison checks:

- table existence;
- required key columns and duplicate keys;
- missing or extra columns after exclusions;
- missing or extra keyed rows;
- exact null, identifier, text, integer, and categorical equality;
- numeric equality within `abs(actual - expected) <= abs_tol +
  rel_tol * abs(expected)`.

Policies are explicit per example. A small default tolerance is allowed, but
scientifically important fields may override it per column. Volatile metadata is
ignored only when named in the manifest. The report must never hide an entire
unexpected table or column merely because it lacks a configured tolerance.

The first terminal report includes counts by difference type and a bounded sample
of mismatched cells. The complete machine-readable comparison remains in the run
workspace.

## CLI surface

The first version uses standard-library `argparse`; no additional CLI framework
is needed for four commands.

```text
fvs-test engines
fvs-test examples
fvs-test run --engine ENGINE --example EXAMPLE [--timeout SECONDS]
fvs-test compare --example EXAMPLE --actual PATH [--expected PATH]
```

`run` automatically compares when the example declares a known output database.
`compare` supports rechecking a retained output without rerunning an engine.

Human-readable output is the default. `--json` may be added to commands that
already have stable result models; it is not required before those models exist.

Exit behavior:

- `0`: requested operation completed and any comparison passed;
- `1`: engine failure, timeout, invalid output, or comparison mismatch;
- `2`: command-line usage error from `argparse`.

Detailed failure classification remains in `run.json` rather than creating a
large public exit-code taxonomy.

## Failure handling

- Missing engine: print the failed probe and configuration locations checked.
- Incompatible example: fail before creating an engine process.
- Timeout: terminate the child, retain logs and inputs, and mark the run timed
  out. Process-tree termination may be added only when a real engine demonstrates
  the need.
- Nonzero/Fortran stop code: let the adapter interpret known engine behavior, but
  require expected output artifacts before declaring success.
- Missing or malformed output DB: report execution separately from output
  validation; preserve the DB for inspection.
- Comparison mismatch: treat it as a scientific test failure, not an engine
  crash.
- DuckDB/SQLite error: identify the database and table involved without dumping
  binary or sensitive content.

No automatic retries are included. A retry could hide nondeterminism or runtime
instability and should be an explicit later experiment.

## Testing strategy

### Unit tests

- Parse and validate example and engine configuration.
- Reject paths escaping an example directory.
- Test adapter argument vectors and probes with injected process results.
- Test workspace isolation and run metadata on success, failure, and timeout.
- Test DuckDB comparison for exact matches, tolerances, nulls, schema drift,
  missing rows, duplicate keys, ignored columns, and readable samples.

### CLI integration tests

A tiny fake engine executable accepts the same conceptual keyfile argument and
writes deterministic logs and SQLite output. Tests invoke the installed
`fvs-test` entrypoint end to end for pass, mismatch, failure, and unavailable
engine cases.

### Live engine tests

Live tests are marked and skipped unless their engine configuration is present.
They run one process at a time with explicit timeouts and single-thread environment
limits. Initial qualification targets the small `thinba` file-backed example,
then one redistributable or synthetic database-backed stand.

Expected scientific output must record its generating engine, version, variant,
command, source data provenance, and regeneration procedure. Unknown or
non-redistributable databases are not committed.

## Tooling and CI

The Python template at `~/templates/python/default` was inspected. It contains a
README directing projects to initialize with `uv`; it does not contain a
Makefile or code scaffold. This repository will therefore use `uv init` in place
and add the smallest project-specific Makefile needed for:

```text
make install
make format
make lint
make typecheck
make test
make check
make run ENGINE=fvsjl EXAMPLE=thinba
```

Exact commands follow the generated `pyproject.toml` and configured tools. The
initial development stack is `pytest`, Ruff, and `ty`, with DuckDB as the required
runtime dependency.

GitHub Actions runs `make check` on a supported Python version using `uv` and
does not download or build FVS engines. CI proves the harness through fake-engine
and SQLite fixture tests. A manual or self-hosted live-engine workflow can be
added after engine licensing, runtime installation, and resource limits are
settled.

There is no deployable service in this milestone, so continuous deployment is
not applicable. Package publication or container release is a later explicit
decision; CI should not pretend that a deployment target exists.

## Documentation and durable context

The README will document installation, local engine configuration, the four CLI
commands, run workspace contents, and how to add an example or engine. Each real
example records provenance and regeneration. `notes/README.md` indexes the
architecture decision and unresolved live-engine qualification work.

The HTML architecture review is committed under `docs/architecture/` so the
Architecture A decision and Architecture C direction can be revisited visually.

## Development sequence

1. Bootstrap the `uv` package, Makefile, CI, and CLI skeleton.
2. Implement models, catalogs, manifest validation, and fake fixtures with tests.
3. Implement isolated subprocess runs and durable run records with tests.
4. Implement `sqlite3` extraction and DuckDB comparison with tests.
5. Add FVSjl and native executable adapters and qualify the `thinba` example.
6. Specify and probe Windows rFVS; run the live smoke test when the host is
   available.
7. Document evidence, gaps, and the next bounded design cycle.

Each step must leave `make check` passing. Live engine failure does not block the
harness from being complete, but it must remain visible as a documented
qualification gap.

## Future evolution toward orchestration

After serial adapters and result contracts are stable, a separate design cycle
may introduce container-backed adapters, a bounded worker pool, and remote job
execution. The invariant is that the catalog, example, `RunRequest`, `RunResult`,
workspace artifacts, and comparison service remain engine-neutral.

Parallel correctness must first establish that repeated serial and concurrent
runs produce equivalent normalized outputs and isolated artifacts. Checkpoint
and state-mutation work follows as a separate capability because it changes the
engine contract from whole-run execution to resumable state transitions.

## Risks and mitigations

- **Engines accept superficially similar but semantically different inputs.**
  Adapters validate capabilities, examples name variants and provenance, and
  unsupported combinations fail explicitly.
- **FVS processes can retain global state or crash.** The first design uses one
  subprocess per run and never loads Fortran or R engine state into the CLI.
- **Numeric tolerances hide regressions.** Tolerances are versioned with examples,
  field-specific where needed, and all accepted differences remain countable.
- **Machine paths leak into reproducible fixtures.** Inputs are copied to isolated
  workspaces and local installations live only in ignored configuration.
- **Known databases are too large or cannot be redistributed.** Start with small,
  provenance-safe fixtures and document generation rather than committing
  unreviewed data.
- **Container goals pull complexity into the first milestone.** Preserve plain
  run contracts and defer execution-backend abstraction until a real second
  backend requires it.

## Open implementation evidence

The architecture is decided. These are qualification tasks, not design
ambiguities:

- select or generate a redistributable database-backed example;
- confirm which output tables and keys are stable for the first scientific gate;
- record the exact local `fvs-modern` executable once it is built or installed;
- confirm Windows-host availability before running the rFVS smoke test;
- measure whether process-tree termination is necessary for any engine timeout.
