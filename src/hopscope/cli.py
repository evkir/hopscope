"""hopscope command-line interface."""

from __future__ import annotations

import argparse
import asyncio

from hopscope import __version__
from hopscope.range.levels import LEVELS
from hopscope.range.scenarios import SCENARIOS


def _base(p: argparse.ArgumentParser) -> None:
    p.add_argument("--transport", choices=("inproc", "a2a"), default="inproc")
    p.add_argument("--authority", choices=("T0", "T1", "T2"), default="T2", help="executor capability set C(A)")


def _chain(p: argparse.ArgumentParser) -> None:
    _base(p)
    p.add_argument("--level", choices=tuple(LEVELS), default="A0", help="attenuation level")
    p.add_argument("--scenario", choices=tuple(SCENARIOS), default=None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hopscope", description=__doc__)
    parser.add_argument("--version", action="version", version=f"hopscope {__version__}")
    sub = parser.add_subparsers(dest="command")
    _chain(sub.add_parser("demo", help="run the deterministic demo chain and print its trace"))
    run = sub.add_parser("run", help="run a deterministic ensemble of the demo and print CIR/ESR/EXR")
    run.add_argument("--n", type=int, default=10)
    _chain(run)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    from hopscope.range.demo import run_demo, run_demo_ensemble, summarize
    from hopscope.tools.authority import tier

    authority = tier(int(args.authority[1]))
    if args.command == "demo":
        run_ = run_demo(args.transport, authority=authority, level=args.level, scenario=args.scenario)
        print("\n".join(summarize(asyncio.run(run_))))
        return 0
    if args.n < 1:
        parser.error("--n must be >= 1")
    from hopscope.meter.metrics import ensemble_metrics, format_ensemble, run_metrics

    runs = asyncio.run(
        run_demo_ensemble(args.n, args.transport, authority=authority, level=args.level, scenario=args.scenario)
    )
    print(format_ensemble(ensemble_metrics([run_metrics(r) for r in runs])))
    return 0
