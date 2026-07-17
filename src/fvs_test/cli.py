from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from fvs_test.application import Application, ApplicationError, RunOutcome
from fvs_test.catalog import CatalogError
from fvs_test.comparison import ComparisonError, ComparisonResult
from fvs_test.config import ConfigError
from fvs_test.engines.base import EngineStatus, EngineValidationError, RunStatus
from fvs_test.models import Example


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fvs-test")
    root = _repository_root()
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument("--engine-config", type=Path)
    parser.add_argument("--local-config", type=Path)
    parser.add_argument("--runs-root", type=Path)
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


def main(
    argv: Sequence[str] | None = None,
    *,
    application: Application | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        app = application or Application.from_paths(
            args.repo_root,
            args.engine_config or args.repo_root / "config" / "engines.toml",
            args.local_config or args.repo_root / "fvs-test.local.toml",
            args.runs_root or args.repo_root / ".runs",
        )
        if args.command == "engines":
            _print_engines(app.engine_statuses())
            return 0
        if args.command == "examples":
            _print_examples(app.example_catalog())
            return 0
        if args.command == "run":
            return _print_run(app.run(args.engine, args.example, args.timeout))
        result = app.compare(
            args.example,
            Path(args.actual),
            Path(args.expected) if args.expected else None,
        )
        _print_comparison(result)
        return 0 if result.equivalent else 1
    except (
        ApplicationError,
        CatalogError,
        ComparisonError,
        ConfigError,
        EngineValidationError,
        OSError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _print_engines(statuses: tuple[EngineStatus, ...]) -> None:
    for status in statuses:
        availability = "available" if status.available else "unavailable"
        print(
            f"{status.name}\t{availability}\t{status.version or '-'}\t{status.diagnostic}"
        )


def _print_examples(examples: tuple[Example, ...]) -> None:
    for example in examples:
        baseline = "baseline" if example.expected_db is not None else "no-baseline"
        print(f"{example.name}\t{example.variant}\t{baseline}\t{example.description}")


def _print_run(outcome: RunOutcome) -> int:
    print(f"workspace: {outcome.run.workspace}")
    print(f"status: {outcome.run.status.value}")
    if outcome.run.diagnostic:
        print(f"diagnostic: {outcome.run.diagnostic}")
    if outcome.comparison is not None:
        _print_comparison(outcome.comparison)
    if outcome.run.status is not RunStatus.SUCCESS:
        return 1
    if outcome.comparison is not None and not outcome.comparison.equivalent:
        return 1
    return 0


def _print_comparison(result: ComparisonResult) -> None:
    label = "equivalent" if result.equivalent else "different"
    print(f"comparison: {label}")
    if result.equivalent:
        return
    counts = ", ".join(f"{kind}={count}" for kind, count in result.counts().items())
    print(f"differences: {counts}")
    for difference in result.differences[:20]:
        location = ".".join(
            item
            for item in (difference.table, difference.row_key, difference.column)
            if item
        )
        print(f"- {difference.kind}: {location}")


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


if __name__ == "__main__":
    raise SystemExit(main())
