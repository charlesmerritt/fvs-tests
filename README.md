# FVS Interface Tests

A serial Python CLI for running the same example through multiple Forest
Vegetation Simulator engines, retaining every run, and comparing SQLite output
against a known baseline with explicit tolerances.

The current architecture is intentionally small: named example bundles feed
typed engine adapters behind one run contract. Container-backed and parallel
execution can reuse that boundary later; they are not part of this milestone.

## Quick start

Prerequisites are Python 3.12+ and
[`uv`](https://docs.astral.sh/uv/). FVS engines are optional: listing examples,
database comparison, and the deterministic test suite work without local FVS
installations.

```bash
uv sync --locked --all-groups
uv run fvs-test engines
uv run fvs-test examples
uv run fvs-test run --engine fvsjl --example thinba
```

The equivalent Make targets are:

```bash
make install
make check
make run ENGINE=fvsjl EXAMPLE=thinba
```

## Configure engines

[`config/engines.toml`](config/engines.toml) defines the engine identities and
their default local paths. Put machine-specific path overrides in the ignored
`fvs-test.local.toml`:

```toml
[engines.fvsjl]
executable = "/path/to/julia"
project = "/path/to/FVSjl"

[engines.official-sn]
executable = "/path/to/FVSsn"
```

Run `uv run fvs-test engines` to see which configured engines are currently
available and why an engine cannot be used. The shipped adapters are:

- `fvsjl`: Julia plus the FVSjl command-line runner.
- `native`: official FVS and `fvs-modern` executables using
  `--keywordfile=<path>`.
- `windows-rfvs`: Windows `Rscript.exe`, rFVS, and a variant DLL through WSL.
  Its `--runs-root` must be on a `/mnt/<drive>/...` path visible to Windows.

Configuration selects trusted adapters and installations; it does not accept
arbitrary shell command templates.

## Run an example

```bash
uv run fvs-test run \
  --engine official-sn \
  --example thinba \
  --timeout 120
```

Every invocation gets an isolated `.runs/<run-id>/` workspace containing copied
inputs, discovered engine outputs, `stdout.log`, `stderr.log`, and `run.json`.
Failed and timed-out runs are retained for diagnosis. Only one engine subprocess
runs at a time, with no retry or background worker.

Global path options precede the command when needed:

```bash
uv run fvs-test \
  --engine-config config/engines.toml \
  --local-config fvs-test.local.toml \
  --runs-root /mnt/c/FVS/fvs-tests-runs \
  run --engine windows-rfvs --example thinba
```

## Compare SQLite outputs

An example can declare an `expected_db` and the tables, row keys, ignored
columns, and tolerances to compare. A successful run then compares automatically
and writes `comparison.json`. An existing output can also be checked directly:

```bash
uv run fvs-test compare \
  --example my-case \
  --actual .runs/<run-id>/FVSOut.db
```

Use `--expected path/to/other.db` to override the example baseline. SQLite is
opened read-only; DuckDB performs the keyed comparison. Text, integer, blob,
null, and key values are exact. Floating-point values pass when:

```text
abs(actual - expected) <= absolute_tolerance + relative_tolerance * abs(expected)
```

Tables are compared only when explicitly declared; a comparison policy with no
declared tables is rejected rather than reported as equivalent. A minimal
manifest section looks like:

```toml
expected_db = "expected/FVSOut.db"

[comparison]
default_absolute_tolerance = 1.0e-6
default_relative_tolerance = 1.0e-6

[comparison.tables.FVS_Summary2]
keys = ["CaseID", "Year", "MgmtID"]
ignore_columns = ["GeneratedAt"]

[comparison.tables.FVS_Summary2.tolerances.Volume]
absolute = 1.0
relative = 0.001
```

Do not add a baseline without recording its engine, version, invocation, source,
and redistribution basis.

## Add an example or engine

Add examples under `examples/<name>/` with an `example.toml`, documented
provenance, and only the declared input/baseline assets. Paths may not escape the
bundle. [`examples/thinba/`](examples/thinba/) is the first real smoke fixture.

Add an engine by implementing the small protocol in
[`src/fvs_test/engines/base.py`](src/fvs_test/engines/base.py), registering its
trusted adapter name in the engine factory/config parser, and testing probe,
validation, argument-vector construction, accepted exit codes, and artifact
discovery. Keep comparison policy outside adapters.

## Tests and CI

```bash
make check
```

This runs Ruff, ty, and pytest. GitHub Actions runs only deterministic unit and
fake-engine integration tests. Real engines are opt-in and always serial:

```bash
FVS_TEST_LIVE=1 uv run pytest tests/integration/test_live_engines.py \
  -m live_engine -k fvsjl -q

FVS_TEST_LIVE=1 uv run pytest tests/integration/test_live_engines.py \
  -m live_engine -k fvs_modern -q

FVS_TEST_LIVE=1 \
FVS_TEST_WINDOWS_RUNS_ROOT=/mnt/c/FVS/fvs-tests-runs \
uv run pytest tests/integration/test_live_engines.py \
  -m live_engine -k windows -q
```

Run each live selection separately. Do not automatically retry a crash or
timeout; inspect the retained workspace first.

There is no continuous-deployment target because this repository does not yet
publish a package or operate a service.

## Architecture and status

- [Approved design](docs/superpowers/specs/2026-07-16-unified-fvs-cli-design.md)
- [Architecture review](docs/architecture/fvs-cli-architecture-review.html)
- [Implementation plan](docs/superpowers/plans/2026-07-17-unified-fvs-cli.md)
- [Durable project notes](notes/README.md)

The next scientific milestone is a reviewed SQLite baseline with stable table
keys and tolerances. Parallel scheduling, containers, checkpoints, and Python
state mutation remain explicit later phases.
