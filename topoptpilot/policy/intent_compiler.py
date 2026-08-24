"""Deterministic scientific-intent compiler.

The agent decides what question to answer. This module decides which bounded,
controlled FEM configurations are legal ways to answer it.
"""

from __future__ import annotations

import uuid
from typing import Any

from topoptpilot.solver_profiles import DirectSolverPolicy
from topoptpilot.policy.doe_templates import discriminating_experiments
from topoptpilot.policy.safety_guard import evaluate_safety
from topoptpilot.schemas import ExperimentProposal, IntentRequest, IntentType, SafetyStatus


class IntentCompiler:
    def __init__(self, solver_policy: DirectSolverPolicy | None = None):
        self.solver_policy = solver_policy or DirectSolverPolicy()

    def compile(self, research: dict[str, Any], experiments: list[dict[str, Any]],
                request: IntentRequest | dict[str, Any]) -> list[ExperimentProposal]:
        intent = request if isinstance(request, IntentRequest) else IntentRequest.model_validate(request)
        source = self._source(experiments, intent.source_experiment)
        base = self._base_parameters(research, source)
        candidates: list[tuple[str, dict[str, Any], list[str], bool]] = []

        if intent.intent == IntentType.ESTABLISH_BASELINE:
            params = {**base, "beta": 1.0, "rmin": 1.5, "penal": 3.0}
            candidates.append(("Establish a reproducible direct MATLAB baseline", params,
                               ["baseline"], False))
        elif intent.intent == IntentType.EXPLORE_PARAMETER:
            factor = intent.factor or "beta"
            levels = self._levels(factor, base)
            for value in levels:
                params = {**base, factor: value}
                candidates.append((f"Explore {factor}={value}", params, [factor], False))
        elif intent.intent == IntentType.REDUCE_GRAYNESS:
            current_beta = float(base.get("beta", 1.0))
            # Pick the smallest novel beta above the current value so the
            # REDUCE proposal is not collapsed by dedup against EXPLORE siblings.
            existing_betas = {
                float((item.get("parameters") or {}).get("beta", 0))
                for item in experiments
                if int(item.get("dimension") or self.solver_policy.dimension(research)) ==
                self.solver_policy.dimension(research)
            }
            new_beta = min(32.0, max(current_beta + 1.0, current_beta * 3))
            while new_beta in existing_betas and new_beta < 32.0:
                new_beta = min(32.0, new_beta * 1.5)
            new_beta = min(32.0, max(2.0, new_beta))
            params = {**base, "beta": new_beta}
            candidates.append(("Reduce grayness with one bounded projection step",
                               params, ["beta"], False))
        elif intent.intent == IntentType.RESTORE_CONNECTIVITY:
            beta_params = {**base, "beta": max(1.0, float(base.get("beta", 8)) / 2)}
            radius_params = {**base, "rmin": min(4.0, float(base.get("rmin", 1.5)) + .5)}
            candidates.append(("Test whether gentler projection restores connectivity",
                               beta_params, ["beta"], False))
            candidates.append(("Test whether a wider filter restores connectivity",
                               radius_params, ["rmin"], False))
        elif intent.intent == IntentType.TEST_COMPETING_EXPLANATIONS:
            template = self._template(intent)
            for item in discriminating_experiments(template, base):
                candidates.append((item["purpose"], item["parameters"],
                                   item["controlled_factors"], False))
        elif intent.intent == IntentType.VERIFY_CANDIDATE:
            candidates.append(("Verify the candidate with a refined direct solver profile", base,
                               ["solver_profile"], True))

        proposals = []
        existing = {(int(item.get("dimension") or self.solver_policy.dimension(research)),
                     tuple((item.get("solver_profile") or {}).get("grid", [])),
                     self._parameter_key(item.get("parameters", {}))) for item in experiments}
        dimension = self.solver_policy.dimension(research)
        for purpose, parameters, factors, verify in candidates:
            parameters.update(research.get("locks", {}))
            profile = self.solver_policy.profile(research, verify=verify)
            grid = list(profile["grid"])
            parameters["grid3d" if dimension == 3 else "grid2d"] = grid
            parameters["max_iter"] = int(profile["max_iterations"])
            if (dimension, tuple(grid), self._parameter_key(parameters)) in existing:
                continue
            safety = evaluate_safety(parameters)
            status = SafetyStatus.PASS if safety["safe"] else SafetyStatus.REJECTED
            proposals.append(ExperimentProposal(
                id=f"P-{uuid.uuid4().hex[:10].upper()}", research_id=research["id"],
                intent=intent.intent, purpose=purpose, fidelity="DIRECT",
                dimension=dimension, solver_profile=profile,
                backend="MATLAB_MCP", parameters=parameters,
                estimated_cost=float(profile["estimated_seconds"]),
                estimated_seconds=float(profile["estimated_seconds"]),
                estimated_memory_mb=float(profile["estimated_memory_mb"]),
                execution_mode=str(research.get("mode", "COPILOT")),
                risk=str(safety["risk"]), safety_status=status,
                approval_required=research.get("mode") == "COPILOT",
                source_experiment=source.get("id") if source else None,
                controlled_factors=factors,
            ))
        return proposals

    @staticmethod
    def _parameter_key(parameters: dict[str, Any]) -> tuple:
        return tuple(sorted((key, repr(value)) for key, value in parameters.items()
                            if key != "initial_density"))

    @staticmethod
    def _source(experiments: list[dict[str, Any]], requested: str | None) -> dict | None:
        if requested:
            return next((item for item in experiments if item["id"] == requested), None)
        completed = [item for item in experiments if item.get("result")]
        return completed[-1] if completed else (experiments[-1] if experiments else None)

    @staticmethod
    def _base_parameters(research: dict[str, Any], source: dict | None) -> dict[str, Any]:
        if source:
            return dict(source["parameters"])
        constraints = research.get("constraints", {})
        return {"volfrac": float(constraints.get("volume_fraction", 0.4)), "rmin": 1.5,
                "penal": 3.0, "beta": 1.0, "max_iter": 80}

    @staticmethod
    def _levels(factor: str, base: dict[str, Any]) -> list[float]:
        if factor == "beta":
            return [2.0, 4.0, 8.0]
        if factor == "rmin":
            return [1.25, 1.75, 2.25]
        if factor == "penal":
            return [2.0, 3.0, 4.0]
        raise ValueError(f"Unsupported exploration factor: {factor}")

    @staticmethod
    def _template(intent: IntentRequest) -> str:
        factors = set(intent.factors)
        if factors == {"beta", "rmin"} or not factors:
            return "beta_vs_rmin"
        if factors == {"beta", "penal"}:
            return "beta_vs_penal"
        if factors == {"projection", "controller"}:
            return "projection_vs_controller"
        raise ValueError("No controlled DOE template exists for the requested factors")
