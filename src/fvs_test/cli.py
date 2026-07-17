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
