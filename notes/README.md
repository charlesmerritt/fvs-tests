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
- Qualify FVSjl and a native official/FVS-modern executable against the `thinba` example.
- Qualify the Windows rFVS adapter when the host runtime is available.
