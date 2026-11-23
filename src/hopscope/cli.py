"""hopscope command-line interface."""

from __future__ import annotations

import argparse
import asyncio
import sys

from hopscope import __version__
from hopscope.harness.llm_client import LIVE_MODELS
from hopscope.range.levels import LEVELS
from hopscope.range.scenarios import SCENARIOS


def _base(p: argparse.ArgumentParser) -> None:
    p.add_argument("--transport", choices=("inproc", "a2a"), default="inproc")
    p.add_argument("--authority", choices=("T0", "T1", "T2"), default="T2", help="executor capability set C(A)")


def _chain(p: argparse.ArgumentParser) -> None:
    _base(p)
    p.add_argument("--level", choices=tuple(LEVELS), default="A0", help="attenuation level")
    p.add_argument("--scenario", choices=tuple(SCENARIOS), default=None)


def _report(results: list) -> None:  # type: ignore[type-arg]
    from hopscope.meter.exploratory import format_exploratory
    from hopscope.meter.metrics import ensemble_metrics, format_ensemble, run_metrics

    print(format_ensemble(ensemble_metrics([run_metrics(r) for r in results])))
    print(format_exploratory(results))


def _live(args: argparse.Namespace) -> int:
    from hopscope.harness.gpu_guard import GPUBusy
    from hopscope.live.runner import LiveCell, run_live_cell

    cell = LiveCell(args.model, dict(LIVE_MODELS)[args.model], args.scenario, args.level, args.authority)
    try:
        live_runs = asyncio.run(run_live_cell(cell, args.n, transport=args.transport))
    except GPUBusy as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 3
    _report([r.result for r in live_runs])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hopscope", description=__doc__)
    parser.add_argument("--version", action="version", version=f"hopscope {__version__}")
    sub = parser.add_subparsers(dest="command")
    _chain(sub.add_parser("demo", help="run the deterministic demo chain and print its trace"))
    run = sub.add_parser("run", help="run a deterministic ensemble of the demo and print CIR/ESR/EXR")
    run.add_argument("--n", type=int, default=10)
    _chain(run)
    matrix = sub.add_parser("matrix", help="scenario x attenuation-level matrix of CIR/ESR/EXR")
    matrix.add_argument("--n", type=int, default=10)
    _base(matrix)
    live = sub.add_parser("live", help="live ensemble on Ollama; refused while the GPU is reserved for PPD")
    live.add_argument("--model", choices=tuple(m for m, _ in LIVE_MODELS), required=True)
    live.add_argument("--n", type=int, default=5)
    _chain(live)
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
    if args.command == "matrix":
        from hopscope.meter.matrix import format_matrix, run_matrix

        print(format_matrix(asyncio.run(run_matrix(args.n, transport=args.transport, authority=authority))))
        return 0
    if args.command == "live":
        return _live(args)
    runs = asyncio.run(
        run_demo_ensemble(args.n, args.transport, authority=authority, level=args.level, scenario=args.scenario)
    )
    _report(runs)
    return 0
