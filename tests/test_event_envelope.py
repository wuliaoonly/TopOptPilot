from __future__ import annotations

from topoptpilot.memory import ResearchStateStore


def test_research_event_adapter_exposes_common_envelope(tmp_path) -> None:
    store = ResearchStateStore(tmp_path / "research.db")
    store.create_research({
        "id": "R-1", "name": "events", "goal": "test", "constraints": {},
        "mode": "COPILOT", "budget_total": 1,
    })
    event = store.append_event("R-1", "SYSTEM", "READY", "ready")
    assert event["eventId"] == event["event_id"]
    assert event["ownerType"] == "research"
    assert event["ownerId"] == "R-1"
    assert event["timestamp"] == event["created_at"]
    assert isinstance(event["payload"], dict)
