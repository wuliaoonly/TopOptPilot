"""Fast service-level checks for the V5 workspace architecture."""

from __future__ import annotations

import tempfile
from pathlib import Path

from topoptpilot.schemas import ExperimentCreate, ResearchCreate
from topoptpilot.service import ResearchService
from agent.llm.client import PiAgentClient, _build_prompt


def test_research_persists_across_service_restart():
    with tempfile.TemporaryDirectory() as directory:
        service = ResearchService(directory, max_workers=1)
        research = service.create_research(ResearchCreate(name="Persistence"))
        research_id = research["id"]
        service.close()
        restored = ResearchService(directory, max_workers=1)
        assert restored.get_research(research_id)["name"] == "Persistence"
        restored.close()


def test_copilot_direct_proposal_waits_for_approval():
    with tempfile.TemporaryDirectory() as directory:
        service = ResearchService(directory, max_workers=1)
        research = service.create_research(ResearchCreate(budget_total=2))
        proposal = service.tools.policy_compile_intent(
            research["id"], intent="ESTABLISH_BASELINE")[0]
        experiment = service.tools.experiment_submit(
            research["id"], proposal["id"])["experiment"]
        assert experiment["status"] == "WAITING"
        assert experiment["dimension"] == 2
        assert experiment["solver_profile"]["grid"] == [96, 32]
        assert service.store.list_decisions(research["id"])[0]["status"] == "PENDING"
        service.close()


def test_commands_compare_lock_report_and_export():
    with tempfile.TemporaryDirectory() as directory:
        service = ResearchService(directory, max_workers=1)
        research = service.create_research(ResearchCreate())
        first = service.create_experiment(research["id"], ExperimentCreate())
        second = service.create_experiment(research["id"], ExperimentCreate())
        assert service.execute_command(research["id"], f"/compare {first['id']} {second['id']}").ok
        assert service.execute_command(research["id"], "/lock beta 8").ok
        assert service.get_research(research["id"])["locks"]["beta"] == 8
        report = service.execute_command(research["id"], "/report")
        export = service.execute_command(research["id"], "/export")
        assert Path(report.data["path"]).exists()
        assert Path(export.data["path"]).exists()
        service.close()


def test_piagent_configuration_and_json_instruction():
    client = PiAgentClient(api_key="test-key", base_url="https://example.invalid",
                           model="qwen3.7-plus")
    assert client.framework == "pi-agent"
    assert client.model == "qwen3.7-plus"
    system, prompt = _build_prompt(
        [{"role": "system", "content": "Return data."},
         {"role": "user", "content": "status"}],
        {"type": "json_object"},
    )
    assert "valid JSON object" in system
    assert "USER" in prompt
