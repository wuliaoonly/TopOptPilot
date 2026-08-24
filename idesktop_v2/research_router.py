"""Research artifact adapters and explicit engineering baseline linking."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from idesktop_v2.artifacts.models import RunStatus
from idesktop_v2.engineering.runs import manager
from idesktop_v2.research_artifacts import build_research_artifact_index, create_source_snapshot
from topoptpilot.api.fastapi_app import service
from topoptpilot.schemas.api_contracts import PromotionRequest

router = APIRouter(prefix="/api/research", tags=["research-artifacts"])


@router.post("/from-engineering-run/{run_id}", status_code=201)
def research_from_engineering_run(run_id: str, request: PromotionRequest) -> dict[str, object]:
    record = manager.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="engineering run not found")
    if record.status is not RunStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="only a completed engineering run can become a research baseline")
    snapshot = create_source_snapshot(record, service.data_dir)
    baseline = {
        "snapshotId": snapshot["snapshotId"],
        "sourceDigest": snapshot["sourceDigest"],
        "originRunId": run_id,
    }
    research = service.create_research({
        "name": request.name,
        "goal": request.goal,
        "budget_total": request.budgetTotal,
        "mode": "COPILOT",
        "constraints": {"engineering_baseline": baseline},
    })
    service.store.append_event(
        research["id"],
        "BASELINE_LINKED",
        "已关联工程运行基线",
        f"工程 Run {run_id} 仅作为证据引用；任何科研实验仍须经过 Intent、Policy 与审批。",
        payload=baseline,
    )
    value = service.get_research(research["id"])
    return {"researchId": research["id"], "snapshot": snapshot, "research": value}


@router.get("/{research_id}/artifacts")
def research_artifacts(research_id: str) -> dict[str, object]:
    try:
        research = service.get_research(research_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return build_research_artifact_index(research, service.data_dir)
