"""Predefined, isolated Pi subagents with mechanically bounded tools."""

from __future__ import annotations

import uuid
from typing import Any

from topoptpilot.memory.research_state import utc_now
from topoptpilot.schemas import AgentRole


ROLE_TOOLS = {
    AgentRole.GUIDE: "research_get_context,knowledge_search,knowledge_get,solver_get_capabilities",
    AgentRole.SCIENTIST: (
        "research_get_context,research_query_history,research_get_budget,knowledge_search,"
        "knowledge_get,solver_get_capabilities,experiment_result,experiment_compare,"
        "failure_get_evidence,policy_compile_intent,experiment_preview"
    ),
    AgentRole.INDEPENDENT_REVIEWER: (
        "research_get_context,research_query_history,research_get_budget,knowledge_search,"
        "knowledge_get,solver_get_capabilities,experiment_result,experiment_compare,"
        "failure_get_evidence,research_get_pareto"
    ),
}

ROLE_RULES = {
    AgentRole.GUIDE: "Explain concepts and elicit missing requirements. Never create or submit experiments.",
    AgentRole.SCIENTIST: "Propose testable competing hypotheses, compile one bounded scientific intent and preview proposals. Never submit.",
    AgentRole.INDEPENDENT_REVIEWER: "Audit evidence, causal control, budget and safety. Return APPROVE, REVISE or REJECT.",
}


def allowed_tools_for_role(role: str) -> set[str]:
    if role == AgentRole.RESEARCH_LEAD.value:
        return set()
    try:
        return set(ROLE_TOOLS[AgentRole(role)].split(","))
    except (KeyError, ValueError):
        return set()


class SubagentCoordinator:
    def __init__(self, bridge):
        self.bridge = bridge

    def dispatch(self, research_id: str, role: str, objective: str,
                 evidence_ids: list[str] | None = None, proposal_id: str | None = None) -> dict[str, Any]:
        self.bridge.service._require_active_research(research_id)
        resolved = AgentRole(role)
        if resolved in {AgentRole.RESEARCH_LEAD} or resolved not in ROLE_TOOLS:
            raise ValueError(f"Role {role} cannot be dispatched")
        task_id = f"SA-{uuid.uuid4().hex[:10].upper()}"
        session_id = f"{self.bridge.sessions.session_id(research_id)}-{task_id.lower()}"
        task = self.bridge.service.store.create_subagent_task({
            "id": task_id, "research_id": research_id, "role": resolved.value,
            "objective": objective, "status": "QUEUED", "evidence_ids": evidence_ids or [],
            "proposal_id": proposal_id, "session_id": session_id,
        })
        locale = self.bridge.service._require_research(research_id).get("locale", "zh-CN")
        language = "Simplified Chinese" if locale == "zh-CN" else "English"
        prompt = (
            f"You are the isolated {resolved.value} Subagent for TopOptPilot task {task_id}.\n"
            f"{ROLE_RULES[resolved]}\nUse {language} for user-visible text. Do not expose chain-of-thought. "
            "Report observation, evidence IDs, verdict/recommendation, reason summary and purpose. "
            "Research State and deterministic Evaluator evidence are authoritative.\n"
            f"Objective: {objective}\nEvidence IDs: {evidence_ids or []}\n"
            f"Proposal ID: {proposal_id or 'none'}"
        )
        self.bridge.start_subagent(task, ROLE_TOOLS[resolved], prompt)
        return self.bridge.service.store.get_subagent_task(task_id)

    def status(self, research_id: str, task_id: str | None = None) -> Any:
        if task_id:
            task = self.bridge.service.store.get_subagent_task(task_id)
            if not task or task["research_id"] != research_id:
                raise KeyError(f"Subagent task {task_id} does not exist")
            return task
        return self.bridge.service.store.list_subagent_tasks(research_id)

    def guide(self, research_id: str, text: str) -> dict[str, Any]:
        return self.dispatch(
            research_id, AgentRole.GUIDE.value,
            "Answer only the user's current simple question. Keep the answer concise (at most 350 "
            "Chinese characters or 220 English words), use no more than two knowledge lookups, and "
            "do not reopen or reconfirm fields already fixed by the Research Contract. If the request "
            "actually requires scientific interpretation or an experiment decision, return exactly "
            f"ESCALATE_TO_LEAD plus one short reason. User question: {text}",
        )

    def scientist(self, research_id: str, objective: str,
                  evidence_ids: list[str] | None = None) -> dict[str, Any]:
        return self.dispatch(research_id, AgentRole.SCIENTIST.value, objective, evidence_ids)
