"""Expose an Agent as an A2A JSON-RPC app and call it through an in-process httpx transport."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
from a2a.client import Client, ClientConfig, create_client
from a2a.helpers import get_message_text
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, SendMessageRequest
from starlette.applications import Starlette

from hopscope.harness.llm_client import LLMBackend
from hopscope.range.a2a_bridge.cards import card_for, hop_url
from hopscope.range.a2a_bridge.codec import (
    CodecError,
    envelope_to_message,
    message_to_envelope,
    reply_message,
    result_from_text,
)
from hopscope.range.agent import Agent, Peer
from hopscope.range.envelope import AgentResult, RunTrace, TaskEnvelope
from hopscope.range.levels import Level
from hopscope.range.roles import Role
from hopscope.tools.gate import Gate
from hopscope.tools.registry import ToolRegistry


class HopExecutor(AgentExecutor):
    """Message-only executor: decode envelope, run the hop, reply with one Message."""

    def __init__(self, agent: Peer) -> None:
        self.agent = agent

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        try:
            env = message_to_envelope(context.message)
        except CodecError as exc:
            result = AgentResult(self.agent.name, ok=False, errors=[f"codec: {exc}"])
        else:
            result = await self.agent.handle(env)
        await event_queue.enqueue_event(reply_message(result, context.context_id))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("hopscope hops are synchronous; cancel is unsupported")


def build_app(agent: Peer, card: AgentCard) -> Starlette:
    handler = DefaultRequestHandler(agent_executor=HopExecutor(agent), task_store=InMemoryTaskStore(), agent_card=card)
    return Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, rpc_url="/")])


class A2APeer:
    """Peer that reaches a hop over A2A JSON-RPC."""

    def __init__(self, card: AgentCard, http: httpx.AsyncClient) -> None:
        self.name = card.name
        self.card = card
        self._http = http
        self._client: Client | None = None

    async def handle(self, env: TaskEnvelope) -> AgentResult:
        if self._client is None:
            self._client = await create_client(self.card, ClientConfig(streaming=False, httpx_client=self._http))
        reply = None
        async for chunk in self._client.send_message(SendMessageRequest(message=envelope_to_message(env))):
            if chunk.HasField("message"):
                reply = chunk.message
        if reply is None:
            return AgentResult(self.name, ok=False, errors=["a2a: response carried no message"])
        try:
            return result_from_text(get_message_text(reply))
        except CodecError as exc:
            return AgentResult(self.name, ok=False, errors=[f"a2a codec: {exc}"])


async def expose(stack: AsyncExitStack, agent: Peer) -> A2APeer:
    card = card_for(agent.name)
    transport = httpx.ASGITransport(app=build_app(agent, card))
    http = await stack.enter_async_context(httpx.AsyncClient(transport=transport, base_url=hop_url(agent.name)))
    return A2APeer(card, http)


@asynccontextmanager
async def a2a_chain(
    llm: LLMBackend,
    registry: ToolRegistry,
    level: Level,
    trace: RunTrace,
    gate: Gate | None = None,
    compromised: frozenset[str] = frozenset(),
) -> AsyncIterator[A2APeer]:
    """Four hops, every edge (user->orchestrator included) over A2A JSON-RPC, no sockets."""
    async with AsyncExitStack() as stack:
        executor = Agent(Role.EXECUTOR.value, Role.EXECUTOR, llm, level, trace, registry=registry, gate=gate)
        peer = await expose(stack, executor)
        for role in (Role.WORKER, Role.PLANNER, Role.ORCHESTRATOR):
            agent = Agent(role.value, role, llm, level, trace, downstream=peer, compromised=role.value in compromised)
            peer = await expose(stack, agent)
        yield peer
