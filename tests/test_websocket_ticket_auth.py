from __future__ import annotations

import time

from topoptpilot.api.ws_tickets import WebSocketTicketBroker


def test_ticket_is_single_use_and_bound_to_owner() -> None:
    broker = WebSocketTicketBroker(ttl_seconds=20)
    ticket = broker.issue("research", "R-1")["ticket"]
    assert broker.consume(ticket, "research", "R-2") is False
    # A cross-owner attempt consumes the capability, preventing probing/replay.
    assert broker.consume(ticket, "research", "R-1") is False
    valid = broker.issue("research", "R-1")["ticket"]
    assert broker.consume(valid, "research", "R-1") is True
    assert broker.consume(valid, "research", "R-1") is False


def test_expired_ticket_is_rejected(monkeypatch) -> None:
    now = [10.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    broker = WebSocketTicketBroker(ttl_seconds=1)
    ticket = broker.issue("engineering_run", "RUN-1")["ticket"]
    now[0] = 11.1
    assert broker.consume(ticket, "engineering_run", "RUN-1") is False
