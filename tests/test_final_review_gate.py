from __future__ import annotations

from topoptpilot.agent_runtime.pi_bridge import _is_final_review_task, _review_verdict


def test_final_review_marker_is_explicit() -> None:
    assert _is_final_review_task({"objective": "FINAL_REVIEW: audit", "proposal_id": None}) is True
    assert _is_final_review_task({"objective": "review final report", "proposal_id": None}) is False
    assert _is_final_review_task({"objective": "FINAL_REVIEW: audit", "proposal_id": "P-1"}) is False


def test_review_verdict_only_reads_first_paragraph() -> None:
    assert _review_verdict("APPROVE\nEvidence is sufficient.\n\nREJECT appears in appendix") == "APPROVE"
    assert _review_verdict("Evidence needs one more control.\n\nAPPROVE") == "REVISE"
    assert _review_verdict("REJECT because the termination claim is unsupported") == "REJECT"
