from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from topoptpilot.agent_runtime.pi_bridge import TOOLS
from topoptpilot.schemas import ResearchCreate
from topoptpilot.service import ResearchService
from topoptpilot.tools import ALLOWED_TOOLS


def _wait(service, experiment_id, seconds=30):
    end = time.time() + seconds
    while time.time() < end:
        value = service.get_experiment(experiment_id)
        if value["status"] in {"SUCCESS", "FAILED"} and value.get("result"):
            return value
        time.sleep(.05)
    raise TimeoutError(experiment_id)


def test_exact_tool_sandbox_and_l3_memory():
    assert set(TOOLS.split(",")) == ALLOWED_TOOLS
    with tempfile.TemporaryDirectory() as directory:
        service = ResearchService(directory, max_workers=1)
        research = service.create_research(ResearchCreate(mode="AUTONOMOUS"))
        context = service.tools.invoke(research["id"], "research_get_context", {})
        assert set(context) >= {"goal", "constraints", "budget", "current_round", "known_failures"}
        try:
            service.tools.invoke(research["id"], "bash", {})
            assert False
        except PermissionError:
            pass
        service.close()


def test_policy_owned_direct_matlab_profile():
    with tempfile.TemporaryDirectory() as directory:
        service = ResearchService(directory, max_workers=1)
        research = service.create_research(ResearchCreate(mode="AUTONOMOUS", budget_total=4))
        proposal = service.tools.policy_compile_intent(
            research["id"], intent="ESTABLISH_BASELINE")[0]
        assert proposal["fidelity"] == "DIRECT"
        assert proposal["backend"] == "MATLAB_MCP"
        assert proposal["solver_profile"]["grid"] == [96, 32]
        assert "grid2d" in proposal["parameters"]
        service.close()


def test_pi_restart_resumes_same_session_without_model_call():
    with tempfile.TemporaryDirectory() as directory:
        service = ResearchService(directory, max_workers=1)
        research = service.create_research(ResearchCreate())
        first = service.pi_runtime.start(research["id"])
        session_id = first.request("get_state")["data"]["sessionId"]
        first.stop()
        service.pi_runtime.processes.pop(research["id"])
        second = service.pi_runtime.resume(research["id"])
        assert second.request("get_state")["data"]["sessionId"] == session_id
        service.close()


def test_three_cases_and_reproduction_bundle():
    root = Path(__file__).parents[1]
    for name in ("case_a_mbb.json", "case_b_cantilever.json", "case_c_failure_recovery.json"):
        assert json.loads((root / "topoptpilot/cases" / name).read_text(encoding="utf-8"))["id"]
    with tempfile.TemporaryDirectory() as directory:
        service = ResearchService(directory, max_workers=1)
        research = service.create_research(ResearchCreate())
        result = service.execute_command(research["id"], "/export")
        assert Path(result.data["path"]).exists()
        service.close()
