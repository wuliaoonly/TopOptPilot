from __future__ import annotations

from topoptpilot.agent_runtime.pi_bridge import _is_final_review_task, _review_verdict
from topoptpilot.service import ResearchService


def test_final_review_marker_is_explicit() -> None:
    assert _is_final_review_task({"objective": "FINAL_REVIEW: audit", "proposal_id": None}) is True
    assert _is_final_review_task({"objective": "review final report", "proposal_id": None}) is False
    assert _is_final_review_task({"objective": "FINAL_REVIEW: audit", "proposal_id": "P-1"}) is False


def test_review_verdict_only_reads_first_paragraph() -> None:
    assert _review_verdict("APPROVE\nEvidence is sufficient.\n\nREJECT appears in appendix") == "APPROVE"
    assert _review_verdict("Evidence needs one more control.\n\nAPPROVE") == "REVISE"
    assert _review_verdict("REJECT because the termination claim is unsupported") == "REJECT"


def test_final_report_stays_blocked_when_reviewer_runtime_is_unavailable(tmp_path) -> None:
    service = ResearchService(tmp_path, enable_agent_runtime=False)
    try:
        research = service.create_research({"name": "review gate", "goal": "verify", "mode": "COPILOT"})
        service.store.update_research(
            research["id"], status="STOPPED", termination_reason="BUDGET_EXHAUSTED",
        )
        result = service._command_report(research["id"])
        assert result.action == "review_pending"
        assert result.ok is False
        assert result.data["reason"] == "reviewer_unavailable"
        assert service.store.get_research(research["id"])["status"] == "PAUSED"
    finally:
        service.close()
