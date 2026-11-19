"""hopscope command-line interface."""

from __future__ import annotations

import argparse

from hopscope import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hopscope", description=__doc__)
    parser.add_argument("--version", action="version", version=f"hopscope {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
