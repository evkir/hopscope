from __future__ import annotations

import pytest

from hopscope.tools.base import ToolCall, ToolError
from hopscope.tools.caps import Capability
from hopscope.tools.payments import SimPayments


def test_transfer_moves_funds_and_labels_destination() -> None:
    p = SimPayments({"treasury": 100})
    call = ToolCall("payments", "transfer", {"to": "acct-attacker", "amount_cents": 40})
    assert p.required(call) == Capability.parse("payments:transfer:acct-attacker")
    p.execute(call)
    assert p.balances == {"treasury": 60, "acct-attacker": 40}
    assert p.ledger == [("treasury", "acct-attacker", 40)]


@pytest.mark.parametrize(
    "args",
    [
        {"to": "x", "amount_cents": 0},
        {"to": "x", "amount_cents": 101},
        {"to": "x", "amount_cents": True},
        {"to": "treasury", "amount_cents": 1},
    ],
)
def test_transfer_rejects(args: dict[str, object]) -> None:
    with pytest.raises(ToolError):
        SimPayments({"treasury": 100}).execute(ToolCall("payments", "transfer", args))


def test_balance() -> None:
    assert SimPayments().execute(ToolCall("payments", "balance", {"account": "treasury"})) == 1_000_000
