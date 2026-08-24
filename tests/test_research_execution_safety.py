from __future__ import annotations

from concurrent.futures import Future
import threading

import pytest
from pydantic import ValidationError

from topoptpilot.schemas import ExperimentCreate, ResearchCreate
from topoptpilot.service import ResearchService


class RecordingMatlabWorker:
    def __init__(self, *, fail: Exception | None = None, block: bool = False) -> None:
        self.fail = fail
        self.block = block
        self.entered = threading.Event()
        self.release = threading.Event()
        self.submissions = 0

    def submit(self, task, research_id, experiment_id, done):
        self.submissions += 1
        self.entered.set()
        if self.block:
            assert self.release.wait(2)
        if self.fail:
            raise self.fail
        return "matlab_real_run_42", Future()

    def close(self) -> None:
        return None


@pytest.fixture
def service(tmp_path):
    value = ResearchService(tmp_path / "research-state", max_workers=1, enable_agent_runtime=False)
    yield value
    value.close()


def research(service: ResearchService, *, budget: int = 4) -> dict:
    return service.create_research(ResearchCreate(
        name="direct execution safety", mode="COPILOT", budget_total=budget,
    ))


def pending_direct(service: ResearchService, research_id: str) -> dict:
    return service.create_experiment(
        research_id, ExperimentCreate(requires_approval=True, backend="MATLAB_MCP"),
    )


def approve(service: ResearchService, experiment: dict) -> None:
    assert service.store.resolve_decision_if_pending(experiment["decision_id"], "APPROVED")


def replace_worker(service: ResearchService, worker: RecordingMatlabWorker) -> None:
    service.matlab_worker.close()
    service.matlab_worker = worker


def test_direct_schema_rejects_non_mcp_backends() -> None:
    for backend in ("simulate", "python", "matlab"):
        with pytest.raises(ValidationError, match="MATLAB_MCP"):
            ExperimentCreate(backend=backend)


def test_service_defensively_rejects_constructed_non_mcp_backend(service: ResearchService) -> None:
    item = research(service)
    unvalidated = ExperimentCreate.model_construct(backend="simulate")
    with pytest.raises(ValueError, match="MATLAB MCP|simulate"):
        service.create_experiment(item["id"], unvalidated)
    assert service.store.list_experiments(item["id"]) == []


def test_persisted_approval_requirement_blocks_direct_run(service: ResearchService) -> None:
    item = research(service)
    experiment = pending_direct(service, item["id"])
    worker = RecordingMatlabWorker()
    replace_worker(service, worker)
    with pytest.raises(ValueError, match="APPROVED"):
        service.run_experiment(experiment["id"])
    assert worker.submissions == 0


def test_concurrent_run_claim_submits_only_once_and_reserves_budget(service: ResearchService) -> None:
    item = research(service)
    experiment = pending_direct(service, item["id"])
    approve(service, experiment)
    worker = RecordingMatlabWorker(block=True)
    replace_worker(service, worker)
    errors: list[BaseException] = []

    def run() -> None:
        try:
            service.run_experiment(experiment["id"])
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    first = threading.Thread(target=run)
    first.start()
    assert worker.entered.wait(1)
    second = threading.Thread(target=run)
    second.start()
    second.join(0.5)
    worker.release.set()
    first.join(2)
    second.join(2)

    assert errors == []
    assert worker.submissions == 1
    assert service.store.get_research(item["id"])["budget_used"] == 1


def test_submit_failure_releases_reserved_budget(service: ResearchService) -> None:
    item = research(service, budget=1)
    experiment = pending_direct(service, item["id"])
    approve(service, experiment)
    replace_worker(service, RecordingMatlabWorker(fail=RuntimeError("worker unavailable")))

    with pytest.raises(RuntimeError, match="worker unavailable"):
        service.run_experiment(experiment["id"])

    persisted = service.store.get_experiment(experiment["id"])
    assert persisted["status"] == "FAILED"
    assert persisted["run_id"].startswith("claim_")
    assert service.store.get_research(item["id"])["budget_used"] == 0


def test_preparation_failure_releases_reserved_budget(service: ResearchService, monkeypatch) -> None:
    item = research(service, budget=1)
    experiment = pending_direct(service, item["id"])
    approve(service, experiment)
    monkeypatch.setattr(service.cache, "get", lambda task: (_ for _ in ()).throw(RuntimeError("cache unavailable")))

    with pytest.raises(RuntimeError, match="cache unavailable"):
        service.run_experiment(experiment["id"])

    assert service.store.get_experiment(experiment["id"])["status"] == "FAILED"
    assert service.store.get_research(item["id"])["budget_used"] == 0


def test_post_submit_persistence_failure_keeps_durable_claim(service: ResearchService, monkeypatch) -> None:
    item = research(service, budget=1)
    experiment = pending_direct(service, item["id"])
    approve(service, experiment)
    worker = RecordingMatlabWorker()
    replace_worker(service, worker)
    original_update = service.store.update_experiment

    def fail_real_run_id(experiment_id: str, **fields):
        if fields.get("run_id") == "matlab_real_run_42":
            raise RuntimeError("database unavailable after submit")
        return original_update(experiment_id, **fields)

    monkeypatch.setattr(service.store, "update_experiment", fail_real_run_id)
    with pytest.raises(RuntimeError, match="database unavailable"):
        service.run_experiment(experiment["id"])

    persisted = service.store.get_experiment(experiment["id"])
    assert worker.submissions == 1
    assert persisted["status"] == "RUNNING"
    assert persisted["run_id"].startswith("claim_")
    assert persisted["error"] is None
    assert service.store.get_research(item["id"])["budget_used"] == 1


def test_decision_resolution_is_compare_and_swap(service: ResearchService) -> None:
    item = research(service)
    experiment = pending_direct(service, item["id"])
    decision_id = experiment["decision_id"]
    assert service.store.resolve_decision_if_pending(decision_id, "REJECTED") is True
    assert service.store.resolve_decision_if_pending(decision_id, "APPROVED") is False
    assert service.store.get_decision(decision_id)["status"] == "REJECTED"
