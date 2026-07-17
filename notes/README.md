# Project notes

## Current decisions

- The first milestone is a serial Python CLI: `fvs-test run --engine <engine> --example <example>`.
- Named example bundles contain input assets, provenance, known output databases, and explicit comparison policies.
- Engines use typed Python adapters behind one engine-neutral run contract.
- DuckDB performs keyed result comparison after read-only SQLite extraction.
- Numeric comparison permits small per-example absolute and relative tolerances; identifiers and categorical values remain exact.
- Container-backed, remote, and parallel execution are the intended evolution, not part of the first milestone.
- Performance benchmarking, checkpoints, and state mutation require later explicit work.

## Design records

- [Unified FVS CLI design](../docs/superpowers/specs/2026-07-16-unified-fvs-cli-design.md)
- [Approved visual architecture review](../docs/architecture/fvs-cli-architecture-review.html)

## Open qualification work

- Select or generate a redistributable SQLite database-backed example.
- Confirm stable comparison tables, keys, and tolerances for the first scientific gate.
- Install or configure `fvs-modern`; its default executable path was unavailable
  during the 2026-07-17 milestone.

## 2026-07-17 implementation milestone

- The installable CLI, typed adapters, isolated runner, example catalog, and
  DuckDB-backed SQLite comparator are implemented.
- The deterministic gate passed with 31 tests; 3 live tests remain skipped by
  default.
- One serial `thinba` smoke passed for FVSjl, the official native SN binary, and
  Windows rFVS. Each used a 120-second timeout and was run separately without
  retries. The Windows test used an isolated `/mnt/c/FVS/fvs-tests-runs` root.
- `thinba` is a smoke input only. It intentionally has no expected database, so
  the live evidence qualifies invocation and artifact capture—not numerical
  equivalence.
- GitHub CI runs deterministic checks only. There is no deployment target for
  this local experiment harness.
