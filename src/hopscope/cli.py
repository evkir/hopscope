"""hopscope command-line interface."""

from __future__ import annotations

import argparse
import asyncio

from hopscope import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hopscope", description=__doc__)
    parser.add_argument("--version", action="version", version=f"hopscope {__version__}")
    sub = parser.add_subparsers(dest="command")
    demo = sub.add_parser("demo", help="run the deterministic A0 demo chain and print its trace")
    demo.add_argument("--transport", choices=("inproc", "a2a"), default="inproc")
    args = parser.parse_args(argv)
    if args.command == "demo":
        from hopscope.range.demo import run_demo, summarize

        print("\n".join(summarize(asyncio.run(run_demo(args.transport)))))
        return 0
    parser.print_help()
    return 0
