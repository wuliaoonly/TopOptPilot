"""V6.3 P0 online Deep Research campaign gate.

Runs a controlled Deep Research campaign against the configured online Agent
service (api.ai-pixel.online / deepseek-v4-flash, credential resolved through
get_qwen_api_key), using the product's own ResearchService + PiBridge runtime.

Coverage required by docs/validation/V6.3-待测试清单.md P0:
  * Research Lead online participation (real Pi RPC turn over FEM evidence).
  * Ordinary Subagent (SCIENTIST) online hypothesis generation.
  * FINAL_REVIEW REVISE and FINAL_REVIEW APPROVE paths.
  * Reviewer gate: the formal final report cannot be generated/downloaded
    before an APPROVE final review.

All experiments are REAL MATLAB MCP runs (no simulation, no cache). Every
recorded ID comes from the real run. Research A exercises the APPROVE path;
Research B exercises the REVISE path via a real uncontrolled comparison that
overclaims causation.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONFIGURED_BASE_URL = "https://api.ai-pixel.online/v1"
CONFIGURED_MODEL = "deepseek-v4-flash"
os.environ["QWEN_BASE_URL"] = CONFIGURED_BASE_URL
os.environ["QWEN_MODEL"] = CONFIGURED_MODEL
os.environ.setdefault("TOPPILOT_RESOURCE_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT))

from topoptpilot.service import ResearchService
from topoptpilot.schemas import ExperimentCreate
from topoptpilot.schemas.api_contracts import ExperimentDraft
from topoptpilot.security.credentials import qwen_api_key_source

DATA_DIR = ROOT / "build" / "v63-online-campaign"


def reset_data_dir() -> None:
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR, ignore_errors=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def wait_until(predicate, timeout: float, interval: float = 2.0, desc: str = ""):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    raise TimeoutError(f"timed out waiting for: {desc}")


def experiment_done(service, experiment_id: str) -> dict | None:
    exp = service.get_experiment(experiment_id)
    if exp["status"] in {"SUCCESS", "FAILED", "CANCELLED"}:
        return exp
    return None


def wait_experiment(service, experiment_id: str, timeout: float = 1200) -> dict:
    return wait_until(lambda: experiment_done(service, experiment_id), timeout,
                      desc=f"experiment {experiment_id} to complete")


def subagent_done(service, research_id: str, task_id: str) -> dict | None:
    for task in service.store.list_subagent_tasks(research_id):
        if task["id"] == task_id and task["status"] in {"COMPLETED", "FAILED"}:
            return task
    return None


def wait_subagent(service, research_id: str, task_id: str, timeout: float = 900) -> dict:
    return wait_until(lambda: subagent_done(service, research_id, task_id), timeout,
                      desc=f"subagent {task_id} to complete")


def lead_idle(service, research_id: str) -> bool:
    session = service.store.get_agent_session(research_id) or {}
    status = session.get("status")
    error = session.get("last_error")
    return status in {"IDLE", "OFFLINE"} and not error


def wait_lead_idle(service, research_id: str, timeout: float = 900) -> None:
    wait_until(lambda: lead_idle(service, research_id), timeout, desc="Research Lead turn to finish")


def latest_final_review_verdict(service, research_id: str) -> str | None:
    for task in reversed(service.store.list_subagent_tasks(research_id)):
        if str(task.get("objective") or "").startswith("FINAL_REVIEW:"):
            text = str((task.get("result") or {}).get("text") or "").lstrip()
            for verdict in ("APPROVE", "REVISE", "REJECT"):
                if text.upper().startswith(verdict):
                    return verdict
    return None


def dispatch_final_review_with_retry(service, research_id: str, *,
                                     max_attempts: int = 4, timeout: float = 900) -> tuple[str, str]:
    """Dispatch the online FINAL_REVIEW reviewer, re-dispatching if the stream dies.

    The OpenAI-compatible endpoint intermittently times out a subagent turn with no
    output. The product retries only the Research Lead, not Subagents, so a failed
    reviewer with no verdict is re-dispatched here. The research stays STOPPED with
    its termination intact, so _command_report re-dispatches cleanly.
    """
    for attempt in range(1, max_attempts + 1):
        command = service._command_report(research_id)
        task_id = command.data.get("task_id")
        task = wait_subagent(service, research_id, task_id, timeout=timeout)
        verdict = latest_final_review_verdict(service, research_id)
        print(f"  final review attempt {attempt}: task={task_id} status={task['status']} "
              f"verdict={verdict}", flush=True)
        if task["status"] == "COMPLETED" or verdict:
            return task_id, verdict
        time.sleep(5)
    raise RuntimeError("final review produced no verdict after retries")


def final_report_ready_event(service, research_id: str) -> dict | None:
    """Formal final report event (distinct from the per-round REPORT_READY)."""
    for event in service.store.list_events(research_id):
        if event.get("event_type") == "REPORT_READY" and event.get("title") == "FINAL REPORT READY":
            return event
    return None


def check_report_blocked(service, research_id: str, stage: str, summary: dict) -> None:
    """The formal final report must be unavailable before an APPROVE final review.

    Per-round reports legitimately emit a REPORT_READY event; the gating
    invariant is that report_path raises FINAL_REPORT_NOT_READY without an
    APPROVE final review and that no FINAL REPORT READY event exists yet.
    """
    assert final_report_ready_event(service, research_id) is None, \
        f"{stage}: FINAL REPORT READY must not exist before APPROVE"
    try:
        service.report_path(research_id)
    except ValueError as exc:
        assert "FINAL_REPORT_NOT_READY" in str(exc), f"{stage}: unexpected error {exc}"
        summary["gate"].append({"stage": stage, "report_blocked": True, "reason": str(exc)[:120]})
    else:
        raise AssertionError(f"{stage}: report_path returned before final approval")


def profile_for(max_iter: int, grid: list[int]) -> dict:
    return {
        "grid": grid, "accuracy": "standard", "variant": "optimized_cpu",
        "acceleration_mode": "vectorized_cpu", "max_iterations": max_iter,
        "estimated_seconds": 120.0, "estimated_memory_mb": 512.0,
    }


def create_run_experiment(service, research_id: str, purpose: str, *,
                          intent: str, beta: float, max_iter: int,
                          grid: list[int] | None = None) -> dict:
    research = service.get_research(research_id)
    dimension = int(str(research["geometry"].get("dimension", "2D")).upper().replace("D", "")) or 2
    grid = grid or [48, 16]
    draft = ExperimentDraft(
        purpose=purpose, dimension=dimension, backend="MATLAB_MCP",
        solverProfile="standard",
        parameters={"volfrac": 0.40, "rmin": 1.5, "penal": 3.0, "beta": beta, "max_iter": max_iter},
        staticWarningsConfirmed=True,
    )
    validation = service.validate_experiment_draft(research_id, draft)
    assert validation["valid"], f"draft invalid: {validation['blockingErrors']}"
    request = ExperimentCreate(
        purpose=purpose, dimension=dimension, backend="MATLAB_MCP",
        solver_profile=profile_for(max_iter, grid), parameters=draft.parameters,
        intent=intent, decision_source="HUMAN", intent_source="HUMAN",
    )
    experiment = service.create_experiment(research_id, request)
    if experiment.get("decision_id"):
        # approve_decision runs the experiment once the decision is APPROVED.
        service.approve_decision(experiment["decision_id"])
    return wait_experiment(service, experiment["id"])


def exp_compact(e: dict) -> dict:
    result = e.get("result") or {}
    return {
        "id": e["id"], "status": e["status"], "intent": e.get("intent"),
        "backend": e.get("backend"),
        "result_source": result.get("result_source"),
        "run_id": e.get("run_id"),
        "compliance": (result.get("objective") or {}).get("compliance"),
        "gray_ratio": (result.get("quality") or {}).get("gray_ratio"),
        "connected_components": (result.get("quality") or {}).get("connected_components"),
        "solver_backend": (result.get("solver") or {}).get("backend"),
        "iterations": (result.get("solver") or {}).get("iterations"),
        "solver_entry_sha256": (result.get("solver") or {}).get("solver_entry_sha256"),
        "evaluation": (result.get("evaluation") or {}).get("success"),
        "evaluator_next_action": (result.get("evaluation") or {}).get("next_action"),
        "artifact_lineage_ids": (result.get("artifacts") or {}).get("lineage_ids", []),
    }


def campaign_summary(service, research_id: str) -> dict:
    research = service.get_research(research_id)
    session = service.store.get_agent_session(research_id) or {}
    hypotheses = service.store.list_hypotheses(research_id)
    return {
        "research_id": research_id,
        "status": research.get("status"),
        "termination_reason": research.get("termination_reason"),
        "agent_session_id": session.get("session_id"),
        "hypotheses": [h["id"] for h in hypotheses],
        "experiments": [exp_compact(e) for e in service.store.list_experiments(research_id)],
        "subagent_tasks": [
            {"id": t["id"], "role": t["role"], "status": t["status"],
             "final_review": str(t.get("objective") or "").startswith("FINAL_REVIEW:"),
             "proposal_id": t.get("proposal_id"),
             "verdict_prefix": ((t.get("result") or {}).get("text") or "").lstrip()[:24]}
            for t in service.store.list_subagent_tasks(research_id)
        ],
    }


def run_research_a(service) -> dict:
    """FINAL_REVIEW APPROVE path: real baseline + verification + online Lead/Subagent/Reviewer."""
    stage = "A/APPROVE"
    summary = {"research_id": None, "gate": []}
    print(f"\n=== {stage} ===", flush=True)

    research = service.create_research({
        "name": "V6.3 online campaign A",
        "goal": "Verify whether a 2D MBB beam reaches a feasible, connected topology at 40% volume "
                "under Heaviside projection, and whether projection strength affects the achieved topology.",
        "description": "Controlled Deep Research campaign A (online). Real MBB MATLAB runs: a beta=16 "
                       "baseline plus a single-variable controlled comparison at beta=32, an online "
                       "Research Lead turn, an online SCIENTIST Subagent, and an online Independent "
                       "Reviewer for the FINAL_REVIEW APPROVE path.",
        "constraints": {"volume_fraction": 0.40, "gray_max": 0.30, "connected": True},
        "budget_total": 4,
        "mode": "COPILOT",
        "geometry": {"type": "MBB", "dimension": "2D", "dimensions": [2.0, 1.0]},
        "material": {"E": 1.0, "nu": 0.3},
        "loads": [{"type": "vertical", "magnitude": 1.0}],
        "boundary_conditions": {"type": "MBB"},
        "hypothesis": "A 2D MBB beam under SIMP with Heaviside projection reaches a feasible, connected "
                      "layout at 40% volume, and projection strength materially affects the achieved topology.",
        "locale": "zh-CN",
    })
    research_id = research["id"]
    summary["research_id"] = research_id
    print(f"  research={research_id}", flush=True)

    e1 = create_run_experiment(service, research_id,
                               "MBB baseline beam at volfrac 0.40 (beta=16)",
                               intent="ESTABLISH_BASELINE", beta=16, max_iter=60)
    assert e1["status"] == "SUCCESS", f"E01 not SUCCESS: {e1['status']} {e1.get('result', {}).get('error')}"
    print(f"  E01 SUCCESS gray={e1['result']['quality']['gray_ratio']:.3f} "
          f"connected={e1['result']['quality']['connected_components']} "
          f"compliance={e1['result']['objective']['compliance']:.1f}", flush=True)

    # Online Research Lead turn over the real E01 evidence.
    service.pi_runtime.send(
        research_id,
        "You are the Research Lead. Read research_get_context and inspect the completed baseline E01. "
        "Interpret the compliance, gray ratio and connectivity evidence, state the scientific "
        "interpretation, and propose the scientific intent of the single next controlled experiment. "
        "Do not write numeric solver parameters.", skill="experiment-planning")
    wait_lead_idle(service, research_id)
    print("  Research Lead online turn completed", flush=True)

    # Online ordinary Subagent: SCIENTIST hypothesis over E01 evidence.
    evidence_ids = (e1.get("result") or {}).get("artifacts", {}).get("lineage_ids", [])
    scientist = service.pi_runtime.subagents.dispatch(
        research_id, "SCIENTIST",
        "Interpret the completed baseline experiment evidence and formulate one falsifiable competing "
        "hypothesis about the effect of projection strength on the achieved topology. Keep it bounded.",
        evidence_ids)
    scientist_done = wait_subagent(service, research_id, scientist["id"])
    scientist_text = str((scientist_done.get("result") or {}).get("text") or "").strip()
    # The OpenAI-compatible stream can end with 'terminated' after a complete
    # answer (the product's partial_stream_recovered case). A substantive result
    # is still usable evidence; a truly empty failure is not.
    assert scientist_done["status"] == "COMPLETED" or scientist_text, \
        f"SCIENTIST produced no result: {scientist_done}"
    summary["scientist_degraded"] = scientist_done["status"] != "COMPLETED"
    print(f"  SCIENTIST subagent {scientist['id']} {scientist_done['status']} "
          f"(degraded={summary['scientist_degraded']})", flush=True)

    e2 = create_run_experiment(service, research_id,
                               "Controlled MBB comparison at higher projection (beta=32)",
                               intent="VERIFY_CANDIDATE", beta=32, max_iter=60)
    assert e2["status"] == "SUCCESS", f"E02 not SUCCESS: {e2['status']} {e2.get('result', {}).get('error')}"
    print(f"  E02 SUCCESS gray={e2['result']['quality']['gray_ratio']:.3f} "
          f"connected={e2['result']['quality']['connected_components']} "
          f"compliance={e2['result']['objective']['compliance']:.1f}", flush=True)

    # Termination on real evidence (natural or explicit).
    termination = service._termination_reason(research_id)
    if not termination:
        service.store.update_research(research_id, status="STOPPED", termination_reason="GOAL_ACHIEVED")
        termination = "GOAL_ACHIEVED"
    print(f"  termination={termination}", flush=True)

    # Reviewer gate: formal report blocked before APPROVE.
    check_report_blocked(service, research_id, f"{stage}: before final review", summary)

    command = service._command_report(research_id)
    assert command.action == "review_pending", f"expected review_pending, got {command.action}"
    review_task_id, verdict = dispatch_final_review_with_retry(service, research_id)
    print(f"  FINAL_REVIEW verdict={verdict}", flush=True)
    summary["final_review_task_id"] = review_task_id
    summary["final_review_verdict"] = verdict

    if verdict != "APPROVE":
        # Real REVISE/REJECT surfaced in the APPROVE campaign: verify correction semantics,
        # run one bounded correction experiment, then re-report to reach APPROVE.
        assert final_report_ready_event(service, research_id) is None, "final report must remain blocked on REVISE"
        check_report_blocked(service, research_id, f"{stage}: after REVISE", summary)
        now = service.get_research(research_id)
        print(f"  REVISE path: status={now['status']} termination={now.get('termination_reason')}", flush=True)
        e3 = create_run_experiment(service, research_id,
                                   "Controlled MBB comparison at intermediate projection (beta=24)",
                                   intent="REVISE_CORRECTION", beta=24, max_iter=60)
        assert e3["status"] == "SUCCESS", f"E03 not SUCCESS: {e3['status']}"
        service.store.update_research(research_id, status="STOPPED", termination_reason="GOAL_ACHIEVED")
        service.store.append_event(research_id, "SYSTEM", "RESEARCH TERMINATED", "GOAL_ACHIEVED")
        review_task_id2, verdict2 = dispatch_final_review_with_retry(service, research_id)
        print(f"  second FINAL_REVIEW verdict={verdict2}", flush=True)
        summary["second_review_task_id"] = review_task_id2
        summary["second_review_verdict"] = verdict2
        if verdict2 != "APPROVE":
            raise AssertionError(f"second final review did not APPROVE: {verdict2}")

    ready = wait_until(lambda: final_report_ready_event(service, research_id), 180,
                       desc="FINAL REPORT READY event after APPROVE")
    assert ready is not None, "FINAL REPORT READY event missing after APPROVE"
    path = service.report_path(research_id)
    assert Path(path).is_file(), f"final report missing: {path}"
    summary["report_markdown"] = str(path)
    print(f"  final report ready: {path}", flush=True)
    return summary


def run_research_b(service) -> dict:
    """FINAL_REVIEW REVISE path: one uncontrolled run + causal overclaim, online reviewer."""
    stage = "B/REVISE"
    summary = {"research_id": None, "gate": []}
    print(f"\n=== {stage} ===", flush=True)

    research = service.create_research({
        "name": "V6.3 online campaign B",
        "goal": "Verify whether a 2D MBB beam reaches a feasible, connected topology at 40% volume "
                "under the configured Heaviside protocol.",
        "description": "Controlled Deep Research campaign B (online). A single uncontrolled real run "
                       "confirms feasibility, but the recorded hypothesis asserts a causal attribution "
                       "(projection strength) that the evidence does not test. The online Independent "
                       "Reviewer must not approve the overclaim and should return REVISE.",
        "constraints": {"volume_fraction": 0.40, "gray_max": 0.30, "connected": True},
        "budget_total": 3,
        "mode": "COPILOT",
        "geometry": {"type": "MBB", "dimension": "2D", "dimensions": [2.0, 1.0]},
        "material": {"E": 1.0, "nu": 0.3},
        "loads": [{"type": "vertical", "magnitude": 1.0}],
        "boundary_conditions": {"type": "MBB"},
        "hypothesis": "Heaviside projection strength causes the final topology to become fully discrete.",
        "locale": "zh-CN",
    })
    research_id = research["id"]
    summary["research_id"] = research_id

    e1 = create_run_experiment(service, research_id,
                               "MBB single uncontrolled run at fixed projection strength",
                               intent="ESTABLISH_BASELINE", beta=16, max_iter=60)
    assert e1["status"] == "SUCCESS", f"E01 not SUCCESS: {e1['status']}"
    print(f"  E01 SUCCESS gray={e1['result']['quality']['gray_ratio']:.3f} "
          f"connected={e1['result']['quality']['connected_components']} "
          f"compliance={e1['result']['objective']['compliance']:.1f}", flush=True)

    # Overclaim: causal termination on an uncontrolled single run.
    service.store.update_research(research_id, status="STOPPED", termination_reason="GOAL_ACHIEVED")
    service.store.append_event(research_id, "SYSTEM", "RESEARCH TERMINATED", "GOAL_ACHIEVED")

    check_report_blocked(service, research_id, f"{stage}: before final review", summary)

    command = service._command_report(research_id)
    assert command.action == "review_pending", f"expected review_pending, got {command.action}"
    review_task_id, verdict = dispatch_final_review_with_retry(service, research_id)
    print(f"  FINAL_REVIEW verdict={verdict}", flush=True)
    summary["final_review_task_id"] = review_task_id
    summary["final_review_verdict"] = verdict

    assert final_report_ready_event(service, research_id) is None, "formal final report must not exist on REVISE"
    check_report_blocked(service, research_id, f"{stage}: after {verdict}", summary)
    now = service.get_research(research_id)
    print(f"  post-review status={now['status']} termination={now.get('termination_reason')}", flush=True)
    # REVISE and REJECT are both non-APPROVE paths: the formal report stays
    # blocked and the termination is withdrawn for correction.
    if verdict in {"REVISE", "REJECT"}:
        assert now["status"] == "READY", f"termination should be withdrawn after {verdict}"
        assert now.get("termination_reason") is None, "termination_reason should be cleared"
    return summary


def main() -> int:
    reset_data_dir()
    source = qwen_api_key_source()
    print(f"agent_key_source={source} data_dir={DATA_DIR}")
    print(f"model={CONFIGURED_MODEL} base_url={CONFIGURED_BASE_URL}", flush=True)

    service = ResearchService(DATA_DIR, enable_agent_runtime=True)
    try:
        health = service.pi_runtime.health() if service.pi_runtime else None
        print(f"pi_health={health}", flush=True)
        if not health or not health.get("available"):
            raise RuntimeError(f"Pi runtime unavailable: {service.pi_runtime_error or health}")
        if health.get("qwen_status") != "CONFIGURED":
            print(f"WARNING: qwen_status={health.get('qwen_status')}", flush=True)

        a = run_research_a(service)
        b = run_research_b(service)

        result = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "model": CONFIGURED_MODEL,
            "base_url": CONFIGURED_BASE_URL,
            "key_source": source,
            "data_dir": str(DATA_DIR),
            "research_a": {**a, "ids": campaign_summary(service, a["research_id"])},
            "research_b": {**b, "ids": campaign_summary(service, b["research_id"])},
        }
        out = ROOT / "build" / "v63-online-campaign.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print("\n=== CAMPAIGN RESULT ===")
        print(json.dumps({"research_a": {"final_review_verdict": a.get("final_review_verdict"),
                                         "report": a.get("report_markdown"),
                                         "gate": a.get("gate")},
                          "research_b": {"final_review_verdict": b.get("final_review_verdict"),
                                         "gate": b.get("gate")}},
                         ensure_ascii=False, indent=2))
        return 0
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        try:
            service.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
