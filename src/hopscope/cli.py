"""hopscope command-line interface."""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

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


#: Test hook: an httpx transport for ``probe`` (None means real HTTP to the checked target).
_PROBE_TRANSPORT: Any = None

#: Test hook: seconds to wait for a chain lab's records after the POST.
_CHAIN_WAIT: float = 5.0


def _default_records() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[2] / "labs" / "dvaa-chain" / "out")


def _probe_chain(args: argparse.Namespace, target: Any) -> int:
    import json
    from pathlib import Path

    import httpx

    from hopscope.probe.chain_run import ChainError, probe_chain
    from hopscope.probe.report import edge_to_dict, format_edge
    from hopscope.targets import TargetRefused

    records = Path(args.records or _default_records())
    try:
        edges = probe_chain(
            target.card_url,
            target.chain_hop,
            records,
            allow_remote=args.allow_remote,
            transport=_PROBE_TRANSPORT,
            wait=_CHAIN_WAIT,
        )
    except TargetRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 3
    except (ChainError, ValueError, OSError, httpx.HTTPError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    dicts = [edge_to_dict(e, target=target.name) for e in edges]
    print(json.dumps(dicts, indent=2) if args.json else "\n".join(format_edge(d) for d in dicts))
    return 0


def _probe(args: argparse.Namespace) -> int:
    import json

    import httpx

    from hopscope.probe.card import CardError
    from hopscope.probe.discover import discover_card
    from hopscope.probe.dvaa import fetch_dvaa_card
    from hopscope.probe.fetch import FetchError, fetch_card
    from hopscope.probe.report import format_report, reading_to_dict
    from hopscope.targets import KNOWN_LOCAL_TARGETS, TargetRefused

    known = {t.name: t for t in KNOWN_LOCAL_TARGETS}.get(args.target)
    if known is not None and known.chain_hop:
        return _probe_chain(args, known)
    try:
        if known is not None and known.dvaa_agent:
            card = fetch_dvaa_card(known.dvaa_agent, dashboard=known.card_url, transport=_PROBE_TRANSPORT)
        else:
            url = known.card_url if known is not None else args.target
            reader = fetch_card if url.endswith(".json") else discover_card
            card = reader(url, allow_remote=args.allow_remote, transport=_PROBE_TRANSPORT)
    except TargetRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 3
    except (FetchError, CardError, httpx.HTTPError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    report = reading_to_dict(card)
    print(json.dumps(report, indent=2) if args.json else format_report(report))
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
    report = sub.add_parser("report", help="write runs.jsonl, hopscope.sarif and report.html for the matrix")
    report.add_argument("--n", type=int, default=10)
    report.add_argument("--out", default="reports")
    _base(report)
    probe = sub.add_parser("probe", help="read an external AgentCard into capabilities and a T0-T2 tier (local only)")
    probe.add_argument("target", help="AgentCard URL (.json), agent base URL, or a known local target (dvaa-a, dvaa-b, dvaa-chain)")
    probe.add_argument("--allow-remote", action="store_true", help="only for systems you are authorised to test")
    probe.add_argument("--json", action="store_true", help="print hopscope.probe/v1 JSON (chain: list of chain/v1)")
    probe.add_argument("--records", default=None, help="chain targets: recorder out/ dir (default: repo lab)")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "probe":
        return _probe(args)
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
    if args.command == "report":
        from pathlib import Path

        from hopscope.report.build import build_report

        paths = asyncio.run(build_report(Path(args.out), args.n, transport=args.transport, authority=authority))
        for kind, path in paths.items():
            print(f"{kind}: {path}")
        return 0
    if args.command == "live":
        return _live(args)
    runs = asyncio.run(
        run_demo_ensemble(args.n, args.transport, authority=authority, level=args.level, scenario=args.scenario)
    )
    _report(runs)
    return 0
