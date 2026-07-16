# Project notes

## Current decisions

- The initial scaffold is test-framework and interface neutral.
- Tests are grouped by interface, then by synchronous or parallel execution mode.
- Reusable FVS cases belong in `tests/fixtures/`; interface-only configuration stays beside its suite.
- Parallel tests target correctness and isolation first. Performance measurements require explicit benchmark tests.

## Open questions

- Which FVS interfaces and versions should be tested first?
- Which baseline cases and variants can be redistributed with the repository?
- Should the common runner use Python/pytest or another framework?
- Which concurrency model is valid for each interface?
