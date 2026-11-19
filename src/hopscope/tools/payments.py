"""Simulated payments ledger. Resource of a transfer is the destination account."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hopscope.tools.base import SimTool, ToolCall, ToolError, get_arg
from hopscope.tools.caps import Domain


class SimPayments(SimTool):
    name = "payments"
    domain = Domain.PAYMENTS
    actions = frozenset({"balance", "transfer"})

    def __init__(self, balances: Mapping[str, int] | None = None, source: str = "treasury") -> None:
        self.source = source
        self.balances: dict[str, int] = dict(balances or {source: 1_000_000})
        self.ledger: list[tuple[str, str, int]] = []

    def resource(self, call: ToolCall) -> str:
        return get_arg(call, "account" if call.action == "balance" else "to")

    def execute(self, call: ToolCall) -> Any:
        if call.action == "balance":
            acct = get_arg(call, "account")
            if acct not in self.balances:
                raise ToolError(f"payments: no such account {acct!r}")
            return self.balances[acct]
        to = get_arg(call, "to")
        amount = get_arg(call, "amount_cents", int)
        if amount <= 0:
            raise ToolError("payments: amount_cents must be > 0")
        if to == self.source:
            raise ToolError("payments: cannot transfer to source account")
        if self.balances.get(self.source, 0) < amount:
            raise ToolError("payments: insufficient funds")
        self.balances[self.source] -= amount
        self.balances[to] = self.balances.get(to, 0) + amount
        self.ledger.append((self.source, to, amount))
        return {"from": self.source, "to": to, "amount_cents": amount}
