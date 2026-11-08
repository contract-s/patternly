"""Patternly: an explain-first tutor for algorithm patterns."""


def main() -> None:
    from .cli import main as cli_main

    raise SystemExit(cli_main())
