"""Fixed-budget solver and agent-quality metrics from authoritative records."""

from __future__ import annotations

def campaign_metrics(experiments: list[dict], events: list[dict] | None = None,
                     decisions: list[dict] | None = None, reference_best: float | None = None) -> dict:
    events, decisions = events or [], decisions or []
    completed = [item for item in experiments if item.get("result")]
    feasible = [item for item in completed if item["status"] == "SUCCESS"]
    best = min((item["result"]["objective"]["compliance"] for item in feasible), default=None)
    best_raw = min((item["result"]["objective"]["compliance"] for item in completed),
                   default=None)
    best_gray_raw = min((item["result"]["quality"].get("gray_ratio", 1)
                         for item in completed), default=None)
    first_feasible = next((index for index, item in enumerate(completed, 1)
                           if item["status"] == "SUCCESS"), None)
    elapsed_seconds = sum(float(item.get("elapsed_seconds") or
                                (item.get("result") or {}).get("solver", {}).get("elapsed_seconds") or 0)
                          for item in completed)
    estimated_seconds = sum(float(item.get("estimated_seconds") or 0) for item in completed)
    signatures, repeats = set(), 0
    for item in experiments:
        signature = (int(item.get("dimension") or 2),
                     repr((item.get("solver_profile") or {}).get("grid")),
                     tuple(sorted((key, repr(value)) for key, value in item["parameters"].items())))
        repeats += signature in signatures
        signatures.add(signature)
    tool_calls = [item for item in events if item.get("kind") == "TOOL_CALL"]
    compile_calls = [item for item in tool_calls if item.get("title") == "policy_compile_intent"]
    rejected = [item for item in events if item.get("kind") == "SAFETY POLICY"
                and "REJECTED" in item.get("title", "")]
    invalid = [item for item in events if item.get("title") == "INVALID INTENT"]
    return {
        "best_feasible_objective": best,
        "experiments_to_feasible": first_feasible,
        "matlab_runs": sum(str(item.get("backend", "matlab")).lower().startswith("matlab")
                           for item in completed),
        "constraint_violation_rate": (None if not completed else
                                      sum(item["status"] != "SUCCESS" for item in completed) / len(completed)),
        # Secondary metrics stay informative even if a short fixed budget never
        # reaches the complete feasibility definition. The primary metric above
        # remains strictly feasibility-gated.
        "best_compliance": best_raw,
        "best_gray_ratio": best_gray_raw,
        "total_compute_seconds": elapsed_seconds,
        "total_estimated_seconds": estimated_seconds,
        "human_interventions": len([item for item in events if item.get("kind") == "HUMAN OVERRIDE"]),
        "final_regret": (None if best is None or reference_best is None else best - reference_best),
        "invalid_intent_rate": (0.0 if not compile_calls else len(invalid) / len(compile_calls)),
        "policy_rejection_rate": (0.0 if not compile_calls else len(rejected) / len(compile_calls)),
        "repeated_experiment_rate": (0.0 if not experiments else repeats / len(experiments)),
        "approval_count": len([item for item in decisions if item.get("status") == "APPROVED"]),
    }
