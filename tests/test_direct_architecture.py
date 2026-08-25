from __future__ import annotations

from pathlib import Path

from topoptpilot.agent_runtime.subagents import ROLE_TOOLS
from topoptpilot.agent_runtime.pi_bridge import _is_final_review_task, _review_verdict
from topoptpilot.schemas import BudgetSpec, ExperimentCreate
from topoptpilot.service import ResearchService


def test_budget_has_no_fidelity_subbudgets() -> None:
    schema = BudgetSpec.model_json_schema()
    assert set(schema["properties"]) == {"total", "time_seconds"}


def test_new_experiment_is_direct_matlab() -> None:
    value = ExperimentCreate(
        research_id="R-1", purpose="baseline", dimension=2,
        solver_profile={"grid": [96, 32], "accuracy": "standard",
                        "variant": "optimized_cpu", "max_iterations": 100},
        parameters={"volfrac": .4}, execution_mode="COPILOT",
    )
    assert value.fidelity == "DIRECT"
    assert value.backend == "MATLAB_MCP"
    assert value.dimension == 2


def test_role_permissions_are_isolated() -> None:
    assert set(ROLE_TOOLS) == {"GUIDE", "SCIENTIST", "INDEPENDENT_REVIEWER"}
    assert "experiment_submit" not in ROLE_TOOLS["GUIDE"]
    assert "policy_compile_intent" in ROLE_TOOLS["SCIENTIST"]
    assert "experiment_submit" not in ROLE_TOOLS["SCIENTIST"]
    assert "experiment_submit" not in ROLE_TOOLS["INDEPENDENT_REVIEWER"]


def test_final_review_is_an_explicit_gate() -> None:
    task = {
        "proposal_id": None,
        "objective": "FINAL_REVIEW: Audit termination reason BUDGET_EXHAUSTED and conclusion.",
    }
    assert _is_final_review_task(task)
    assert _review_verdict("APPROVE\nThe budget is exhausted.") == "APPROVE"
    assert _review_verdict("No leading verdict was returned.") == "REVISE"
    assert not _is_final_review_task({**task, "proposal_id": "P-1"})


def test_copilot_proposal_uses_policy_grid_and_waits(tmp_path: Path) -> None:
    service = ResearchService(tmp_path, max_workers=1)
    try:
        research = service.create_research({
            "name": "Direct", "goal": "baseline", "mode": "COPILOT",
            "geometry": {"type": "MBB", "dimension": "2D"},
            "budget_total": 2, "budgets": {"total": 2, "time_seconds": 600},
        })
        proposal = service.tools.policy_compile_intent(
            research["id"], intent="ESTABLISH_BASELINE")[0]
        assert proposal["fidelity"] == "DIRECT"
        assert proposal["dimension"] == 2
        assert proposal["solver_profile"]["grid"] == [96, 32]
        submitted = service.tools.experiment_submit(research["id"], proposal["id"])
        experiment = submitted["experiment"]
        assert experiment["status"] == "WAITING"
        assert experiment["backend"] == "MATLAB_MCP"
        assert experiment["legacy_fidelity"] is None
    finally:
        service.close()


def test_public_desktop_sources_do_not_show_fidelity_levels() -> None:
    root = Path(__file__).resolve().parents[1]
    sources = "\n".join(path.read_text(encoding="utf-8") for path in
                        (root / "desktop/src").glob("*.tsx"))
    for token in ("F0", "F1", "F2", "F3", "UPGRADE_FIDELITY"):
        assert token not in sources
