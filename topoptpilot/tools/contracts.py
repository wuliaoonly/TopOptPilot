"""Canonical schemas for the complete allowlisted Pi research tool surface."""

from __future__ import annotations

from typing import Any


def _object(properties: dict[str, Any] | None = None, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": False,
    }


STRING = {"type": "string"}
STRING_ARRAY = {"type": "array", "items": STRING}

TOOL_CONTRACTS: dict[str, dict[str, Any]] = {
    "research_get_context": {"description": "Read compact authoritative L3 research context before planning.", "parameters": _object()},
    "research_query_history": {"description": "Retrieve relevant historical experiments and evidence.", "parameters": _object({"query": STRING, "limit": {"type": "number"}}, ["query"])},
    "research_get_budget": {"description": "Read remaining experiment-count and compute-time budgets.", "parameters": _object()},
    "experiment_validate_draft": {"description": "Validate an exact Agent draft before it becomes one human-approvable proposal.", "parameters": _object({"purpose": STRING, "dimension": {"type": "number"}, "solverProfile": STRING, "parameters": _object({}, []), "overlay": _object({}, [])}, ["purpose", "dimension", "solverProfile"])},
    "experiment_preview": {"description": "Preview cost, risk, purpose, and approval requirement without running FEM.", "parameters": _object({"proposal_id": STRING}, ["proposal_id"])},
    "experiment_submit": {"description": "Submit an already compiled safe proposal asynchronously.", "parameters": _object({"proposal_id": STRING}, ["proposal_id"])},
    "experiment_status": {"description": "Read asynchronous experiment status and progress.", "parameters": _object({"experiment_id": STRING}, ["experiment_id"])},
    "experiment_result": {"description": "Read structured final metrics for a completed experiment.", "parameters": _object({"experiment_id": STRING}, ["experiment_id"])},
    "experiment_compare": {"description": "Compute deterministic metric and parameter differences.", "parameters": _object({"a": STRING, "b": STRING}, ["a", "b"])},
    "research_get_pareto": {"description": "Read compliance-versus-gray Pareto candidates.", "parameters": _object()},
    "failure_get_evidence": {"description": "Retrieve experiments supporting a structured failure type.", "parameters": _object({"failure_type": STRING}, ["failure_type"])},
    "knowledge_search": {"description": "Search the versioned offline topology-optimization knowledge base.", "parameters": _object({"query": STRING, "limit": {"type": "number"}, "category": STRING}, ["query"])},
    "knowledge_get": {"description": "Read one cited offline knowledge document.", "parameters": _object({"document_id": STRING}, ["document_id"])},
    "solver_get_capabilities": {"description": "Inspect verified MATLAB 2D/3D profiles and acceleration capabilities.", "parameters": _object()},
    "subagent_dispatch": {"description": "Dispatch a predefined isolated scientific Subagent.", "parameters": _object({"role": STRING, "objective": STRING, "evidence_ids": STRING_ARRAY, "proposal_id": STRING}, ["role", "objective"])},
    "subagent_status": {"description": "Read isolated Subagent task status and result.", "parameters": _object({"task_id": STRING})},
}

ALLOWED_TOOLS = frozenset(TOOL_CONTRACTS)
