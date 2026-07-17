from importlib import import_module


def test_parser_exposes_top_level_commands() -> None:
    cli = import_module("fvs_test.cli")

    parser = cli.build_parser()

    action = next(action for action in parser._actions if action.dest == "command")
    assert action.choices is not None
    assert set(action.choices) == {"engines", "examples", "run", "compare"}
