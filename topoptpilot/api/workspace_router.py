"""Workspace-scoped API projection for the shared Quick/Deep workbench.

The router deliberately stores only project identities.  A filesystem root and
its signed grant stay in the desktop process and are never returned from this
API or persisted in SQLite.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from topoptpilot.api.ws_tickets import broker as ws_ticket_broker
from topoptpilot.schemas.api_contracts import (
    AgentWorkflowItem, QuickAgentTask, Workspace, WorkspaceContextRef,
    WorkspaceConversationMessage, WorkspaceGrant,
)


class WorkspaceCreateRequest(BaseModel):
    project_id: str = Field(alias="projectId", min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)


class WorkspacePatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


class ConversationRequest(BaseModel):
    lane: Literal["quick", "deep", "shared"] = "shared"
    role: Literal["user", "assistant", "system"] = "user"
    content: str = Field(min_length=1, max_length=16_000)
    research_id: str | None = Field(default=None, alias="researchId")


class QuickTaskRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4_000)


def _public_workspace(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": value["id"], "projectId": value["project_id"], "name": value["name"],
        "readOnly": bool(value.get("read_only")), "createdAt": value["created_at"],
        "updatedAt": value["updated_at"],
    }


def _public_message(value: dict[str, Any]) -> dict[str, Any]:
    return {"id": value["id"], "workspaceId": value["workspace_id"], "lane": value["lane"],
            "role": value["role"], "content": value["content"], "researchId": value.get("research_id"),
            "createdAt": value["created_at"]}


def _public_task(value: dict[str, Any]) -> dict[str, Any]:
    return {"id": value["id"], "workspaceId": value["workspace_id"], "status": value["status"],
            "round": value["round"], "prompt": value["prompt"], "result": value.get("result", {}),
            "createdAt": value["created_at"], "updatedAt": value["updated_at"]}


def _public_workflow(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflowItemId": value["id"], "workspaceId": value["workspace_id"], "lane": value["lane"],
        "ownerType": value["owner_type"], "ownerId": value["owner_id"],
        "actorType": value["actor_type"], "actorRole": value["actor_role"], "phase": value["phase"],
        "status": value["status"], "title": value["title"], "summary": value["summary"],
        "createdAt": value["created_at"], "updatedAt": value["updated_at"],
        "relatedRunId": value.get("related_run_id"), "experimentId": value.get("experiment_id"),
        "proposalId": value.get("proposal_id"), "taskId": value.get("task_id"),
        "evidenceIds": value.get("evidence_ids", []), "requiresHumanAction": value.get("requires_human_action", False),
        "sanitizedToolCall": value.get("sanitized_tool_call"), "error": value.get("error"),
    }


def build_workspace_router(service) -> APIRouter:
    router = APIRouter(tags=["workspace"])

    @router.get("/api/workspaces", response_model=list[Workspace], operation_id="list_workspaces")
    def list_workspaces():
        return [_public_workspace(item) for item in service.store.list_workspaces()]

    @router.post("/api/workspaces", response_model=Workspace, status_code=201, operation_id="create_workspace")
    def create_workspace(request: WorkspaceCreateRequest):
        try:
            return _public_workspace(service.store.create_workspace({
                "id": f"WS-{uuid.uuid4().hex[:12].upper()}", "project_id": request.project_id, "name": request.name,
            }))
        except Exception as exc:
            raise HTTPException(status_code=409, detail={"code": "WORKSPACE_CONFLICT", "message": str(exc),
                "source": "API", "retryable": False, "detail": {}}) from exc

    @router.get("/api/workspaces/{workspace_id}", response_model=Workspace, operation_id="get_workspace")
    def get_workspace(workspace_id: str):
        item = service.store.get_workspace(workspace_id)
        if not item:
            raise HTTPException(status_code=404, detail={"code": "WORKSPACE_NOT_FOUND", "message": workspace_id,
                "source": "API", "retryable": False, "detail": {}})
        return _public_workspace(item)

    @router.patch("/api/workspaces/{workspace_id}", response_model=Workspace, operation_id="update_workspace")
    def update_workspace(workspace_id: str, request: WorkspacePatchRequest):
        if not service.store.get_workspace(workspace_id):
            raise HTTPException(status_code=404, detail={"code": "WORKSPACE_NOT_FOUND", "message": workspace_id,
                "source": "API", "retryable": False, "detail": {}})
        return _public_workspace(service.store.update_workspace(workspace_id, **request.model_dump(exclude_none=True)))

    @router.get("/api/workspaces/{workspace_id}/contexts", response_model=list[WorkspaceContextRef],
                operation_id="list_workspace_contexts")
    def list_contexts(workspace_id: str, mode: Literal["quick", "deep"]):
        workspace = service.store.get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail={"code": "WORKSPACE_NOT_FOUND", "message": workspace_id,
                "source": "API", "retryable": False, "detail": {}})
        contexts: list[dict[str, Any]] = [{
            "id": f"draft:{workspace_id}", "type": "workspace_draft", "title": workspace["name"],
            "status": "draft", "workspaceId": workspace_id,
        }]
        if mode == "quick":
            # The run manager remains the source of run details.  Its manifests
            # can be absent after a user clears data, so the workspace projection
            # intentionally degrades to the durable draft rather than inventing a run.
            return contexts
        for research in service.store.list_research(workspace_id=workspace_id):
            contexts.append({"id": research["id"], "type": "research", "title": research["name"],
                "status": research["status"], "workspaceId": workspace_id, "researchId": research["id"]})
            for experiment in service.store.list_experiments(research["id"]):
                contexts.append({"id": experiment["id"], "type": "experiment", "title": experiment["purpose"],
                    "status": experiment["status"], "workspaceId": workspace_id, "researchId": research["id"],
                    "experimentId": experiment["id"], "sourceSummary": "SourceSnapshot → Experiment Overlay"})
        return contexts

    @router.get("/api/workspaces/{workspace_id}/conversation", response_model=list[WorkspaceConversationMessage],
                operation_id="list_workspace_conversation")
    def list_conversation(workspace_id: str):
        return [_public_message(item) for item in service.store.list_workspace_messages(workspace_id)]

    @router.post("/api/workspaces/{workspace_id}/conversation", response_model=WorkspaceConversationMessage,
                 operation_id="add_workspace_conversation")
    def add_conversation(workspace_id: str, request: ConversationRequest):
        if not service.store.get_workspace(workspace_id):
            raise HTTPException(status_code=404, detail={"code": "WORKSPACE_NOT_FOUND", "message": workspace_id,
                "source": "API", "retryable": False, "detail": {}})
        return _public_message(service.store.add_workspace_message({
            "id": f"MSG-{uuid.uuid4().hex[:12].upper()}", "workspace_id": workspace_id, **request.model_dump(),
        }))

    @router.get("/api/workspaces/{workspace_id}/workflow", response_model=list[AgentWorkflowItem],
                operation_id="list_workspace_workflow")
    def list_workflow(workspace_id: str):
        return [_public_workflow(item) for item in service.store.list_workflow_items(workspace_id)]

    @router.post("/api/workspaces/{workspace_id}/quick-agent/tasks", response_model=QuickAgentTask,
                 status_code=202, operation_id="create_quick_agent_task")
    def create_quick_task(workspace_id: str, request: QuickTaskRequest):
        if not service.store.get_workspace(workspace_id):
            raise HTTPException(status_code=404, detail={"code": "WORKSPACE_NOT_FOUND", "message": workspace_id,
                "source": "API", "retryable": False, "detail": {}})
        # Replacement is safe: only unsettled tasks are cancelled; completed patch
        # proposals are preserved for human review and never overwritten.
        for prior in service.store.list_quick_agent_tasks(workspace_id):
            if prior["status"] in {"queued", "running", "preflight"}:
                service.store.update_quick_agent_task(prior["id"], status="cancelled")
        task = service.store.create_quick_agent_task({
            "id": f"QAT-{uuid.uuid4().hex[:12].upper()}", "workspace_id": workspace_id,
            "status": "queued", "round": 1, "prompt": request.prompt,
        })
        service.store.upsert_quick_agent_session(workspace_id, "running")
        service.store.add_workflow_item({"id": f"WF-{uuid.uuid4().hex[:12].upper()}",
            "workspace_id": workspace_id, "lane": "quick", "owner_type": "quick_agent_task",
            "owner_id": task["id"], "actor_type": "agent", "actor_role": "QUICK_AGENT",
            "phase": "queued", "status": "queued", "title": "Quick Agent queued",
            "summary": "The code agent may read only files authorized by the workspace grant.",
            "task_id": task["id"]})
        return _public_task(task)

    @router.get("/api/workspaces/{workspace_id}/quick-agent/tasks/{task_id}", response_model=QuickAgentTask,
                operation_id="get_quick_agent_task")
    def get_quick_task(workspace_id: str, task_id: str):
        item = service.store.get_quick_agent_task(task_id)
        if not item or item["workspace_id"] != workspace_id:
            raise HTTPException(status_code=404, detail={"code": "QUICK_AGENT_TASK_NOT_FOUND", "message": task_id,
                "source": "AGENT", "retryable": False, "detail": {}})
        return _public_task(item)

    @router.post("/api/workspaces/{workspace_id}/quick-agent/tasks/{task_id}/cancel", response_model=QuickAgentTask,
                 operation_id="cancel_quick_agent_task")
    def cancel_quick_task(workspace_id: str, task_id: str):
        item = service.store.get_quick_agent_task(task_id)
        if not item or item["workspace_id"] != workspace_id:
            raise HTTPException(status_code=404, detail={"code": "QUICK_AGENT_TASK_NOT_FOUND", "message": task_id,
                "source": "AGENT", "retryable": False, "detail": {}})
        if item["status"] not in {"patch_proposed", "awaiting_approval", "applied"}:
            item = service.store.update_quick_agent_task(task_id, status="cancelled")
        return _public_task(item)

    @router.post("/api/workspaces/{workspace_id}/stream-ticket", operation_id="create_workspace_stream_ticket")
    def workspace_stream_ticket(workspace_id: str):
        if not service.store.get_workspace(workspace_id):
            raise HTTPException(status_code=404, detail={"code": "WORKSPACE_NOT_FOUND", "message": workspace_id,
                "source": "API", "retryable": False, "detail": {}})
        return ws_ticket_broker.issue("workspace", workspace_id)

    @router.websocket("/api/workspaces/{workspace_id}/stream")
    async def workspace_stream(websocket: WebSocket, workspace_id: str):
        ticket = websocket.query_params.get("ticket", "")
        if not ws_ticket_broker.consume(ticket, "workspace", workspace_id):
            await websocket.close(code=4401)
            return
        if not service.store.get_workspace(workspace_id):
            await websocket.close(code=4404)
            return
        await websocket.accept()
        previous = ""
        try:
            while True:
                items = [_public_workflow(item) for item in service.store.list_workflow_items(workspace_id)]
                fingerprint = repr([(item["workflowItemId"], item["status"], item["updatedAt"]) for item in items])
                if fingerprint != previous:
                    previous = fingerprint
                    await websocket.send_json({"type": "workflow", "items": items})
                await asyncio.sleep(0.5)
        except (WebSocketDisconnect, RuntimeError):
            return

    return router
