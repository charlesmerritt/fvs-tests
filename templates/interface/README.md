# <Interface name>

Describe the FVS interface represented by this directory.

## Environment

- **Interface and version:** `<name and version>`
- **FVS version:** `<version>`
- **FVS variant(s):** `<variants>`
- **Operating system:** `<supported systems>`
- **Parallel model:** `<processes, threads, async tasks, or other>`

## Setup

Document all prerequisites and reproducible setup commands. Do not rely on undeclared machine-local configuration.

## Run

```bash
<command for this interface's tests>
```

## Coverage

| Mode | Cases | What is verified |
| --- | --- | --- |
| Synchronous | `<cases>` | Invocation and normalized outputs |
| Parallel | `<cases>` | Result equivalence and run isolation |

## Interface behavior

Document:

- how inputs are supplied;
- where outputs and logs are written;
- how failures are reported;
- whether the interface is safe for concurrent use;
- any output normalization required before comparison.

## Known limitations

- `<limitation or none>`

## Directory structure

```text
.
├── README.md
├── fixtures/       # Configuration used only by this interface
├── synchronous/    # Single-run baseline tests
└── parallel/       # Concurrent correctness and isolation tests
```
