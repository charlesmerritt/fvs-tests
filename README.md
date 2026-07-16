# FVS Interface Tests

A shared test harness for evaluating Forest Vegetation Simulator (FVS) interfaces in synchronous and parallel execution modes.

## Goals

- Verify that each interface can run representative FVS cases successfully.
- Compare normalized results across interfaces.
- Confirm that parallel execution produces the same results as synchronous execution.
- Detect shared-state, working-directory, and output-collision failures.

Performance benchmarking is out of scope unless a test explicitly records timing or resource metrics.

## Repository structure

```text
.
├── templates/
│   └── interface/          # Copyable skeleton for a new interface
├── tests/
│   ├── fixtures/           # Cases and expected results shared by interfaces
│   └── interfaces/         # One directory per tested interface
└── notes/                  # Design decisions and open questions
```

Each interface directory follows this shape:

```text
tests/interfaces/<interface-name>/
├── README.md               # Setup, versions, commands, and limitations
├── fixtures/               # Interface-specific inputs or configuration
├── synchronous/            # Single-run correctness tests
└── parallel/               # Concurrent-run correctness and isolation tests
```

## Add an interface

1. Copy the skeleton:

   ```bash
   cp -R templates/interface tests/interfaces/<interface-name>
   ```

2. Complete the copied `README.md` with installation and invocation details.
3. Add interface-specific fixtures only when a shared fixture cannot be used directly.
4. Add synchronous tests first to establish expected behavior.
5. Add parallel tests that run the same cases and compare against the synchronous results.
6. Document the test command in the interface README.

## Test contract

All interface suites should follow the same rules:

- Use deterministic inputs and record the FVS variant and version.
- Keep expected scientific outputs separate from logs and timing data.
- Normalize volatile values such as timestamps and temporary paths before comparison.
- Give every invocation an isolated working directory and unique output paths.
- Treat the synchronous result as the baseline for the equivalent parallel run.
- Fail with enough context to identify the interface, case, worker, and retained artifacts.

### Synchronous tests

Synchronous tests run one case at a time. They establish that the interface is configured correctly and provide baseline results for parallel comparisons.

### Parallel tests

Parallel tests run independent cases concurrently using the concurrency model appropriate to the interface (for example, processes, threads, or async tasks). They should verify correctness and isolation, not merely that all calls returned.

## Fixtures

Place reusable FVS inputs and expected normalized outputs in `tests/fixtures/`. Keep interface-specific wrappers, control files, or generated configuration under that interface's local `fixtures/` directory.

Do not commit licensed binaries, credentials, or machine-specific FVS installations.

## Running tests

No test framework or interface dependency has been selected yet. Each interface README must document its setup and test command until a common runner is adopted.

## Status

The repository currently contains the documentation and copyable interface-test structure. Concrete FVS interfaces and baseline cases are the next additions.
