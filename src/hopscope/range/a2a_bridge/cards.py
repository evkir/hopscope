"""AgentCards for the four hops. Hosts use the reserved .test TLD; traffic is in-process."""

from __future__ import annotations

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    AgentInterface,
    AgentSkill,
)

from hopscope import __version__
from hopscope.range.a2a_bridge.codec import MANDATE_EXT

ROLE_DESCRIPTIONS: dict[str, str] = {
    "orchestrator": "Receives the user task and delegates it to the planner.",
    "planner": "Breaks a task into steps and delegates each to the worker.",
    "worker": "Turns a step into a concrete instruction for the executor.",
    "executor": "Executes tool calls against simulated tools.",
}


def hop_url(name: str) -> str:
    return f"http://{name}.hopscope.test/"


def card_for(name: str) -> AgentCard:
    description = ROLE_DESCRIPTIONS[name]
    return AgentCard(
        name=name,
        description=description,
        version=__version__,
        supported_interfaces=[AgentInterface(url=hop_url(name), protocol_binding="JSONRPC", protocol_version="1.0")],
        capabilities=AgentCapabilities(
            streaming=False,
            extensions=[AgentExtension(
                uri=MANDATE_EXT,
                description="Delegated mandate carried in message metadata (A0: unauthenticated claim).",
                required=False,
            )],
        ),
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        skills=[AgentSkill(id=name, name=name, description=description, tags=["hopscope", name])],
    )
