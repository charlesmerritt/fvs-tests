# Legacy interface scaffold

The current architecture uses typed adapters under `src/fvs_test/engines/` and
shared CLI integration tests under `tests/integration/`. New production engine
coverage should be added there.

This directory is retained only as a historical scaffold for isolated exploratory
tests. Do not create a second directory-per-interface abstraction for engines
already supported by the unified CLI.
