"""DVAA adapter: its A2A agents publish no AgentCard, so read them from the dashboard API.

DVAA 0.9.2 (opena2a/dvaa@sha256:edcd7fbb...) answers 404 on /.well-known/agent-card.json and
/.well-known/agent.json for the Orchestrator (:7020) and Worker Agent (:7021). The dashboard's
/agents API lists each agent's description and tool names; this adapter turns one entry into a
ProbeCard with ``source="dvaa-dashboard"`` so a report never presents a synthesized card as one
the agent published. Tools become skills, so the capability grammar reads them like card skills.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import httpx

from hopscope.probe.card import CardError, ProbeCard, parse_card
from hopscope.probe.fetch import fetch_json
from hopscope.targets import check_target

DVAA_IMAGE = "opena2a/dvaa:0.9.2@sha256:edcd7fbb94b28be64527b58f7238384d58d9b0b015b6ab02cd7f816c7f696f45"
DASHBOARD = "http://127.0.0.1:9000/agents"
SOURCE = "dvaa-dashboard"


def card_from_dashboard(doc: Any, agent_id: str) -> ProbeCard:
    agents = doc.get("agents") if isinstance(doc, Mapping) else doc
    if not isinstance(agents, list):
        raise CardError("DVAA /agents must be a list of agents")
    entry = next((a for a in agents if isinstance(a, Mapping) and a.get("id") == agent_id), None)
    if entry is None:
        raise CardError(f"DVAA lists no agent {agent_id!r}")
    tools = entry.get("tools") or []
    if not isinstance(tools, list):
        raise CardError(f"DVAA agent {agent_id!r}: tools must be a list")
    port = entry.get("port")
    card = parse_card({
        "name": entry.get("name") or agent_id,
        "description": entry.get("description"),
        "url": f"http://127.0.0.1:{port}/" if isinstance(port, int) and not isinstance(port, bool) else None,
        "skills": [
            {"id": t, "name": t, "description": t.replace("_", " "), "tags": ["dvaa-tool"]}
            for t in tools
            if isinstance(t, str)
        ],
    })
    return replace(card, source=SOURCE)


def fetch_dvaa_card(
    agent_id: str, *, dashboard: str = DASHBOARD, transport: httpx.BaseTransport | None = None
) -> ProbeCard:
    """Local only: DVAA is intentionally vulnerable and must never be reached remotely."""
    card = card_from_dashboard(fetch_json(dashboard, transport=transport), agent_id)
    for url in card.urls:
        check_target(url)
    return card
