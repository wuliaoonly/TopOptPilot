"""Public API contracts shared by desktop, quick runs, and deep research."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiContract(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ApiError(ApiContract):
    code: str = Field(pattern=r"^[A-Z0-9_]+$")
    message: str
    source: Literal["API", "POLICY", "MATLAB", "RUNTIME", "AGENT", "EVALUATOR"] = "API"
    retryable: bool = False
    detail: dict[str, Any] = Field(default_factory=dict)


class StreamTicket(ApiContract):
    ticket: str
    expires_in: int = Field(alias="expiresIn", gt=0)


class ArtifactRef(ApiContract):
    relative_path: str = Field(alias="relativePath")
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    media_type: str = Field(alias="mediaType")
    size_bytes: int = Field(alias="sizeBytes", ge=0)


class EventEnvelope(ApiContract):
    event_id: str = Field(alias="eventId")
    type: str
    source: str
    timestamp: str
    owner_type: Literal["engineering_run", "research", "experiment"] = Field(alias="ownerType")
    owner_id: str = Field(alias="ownerId")
    run_id: str | None = Field(default=None, alias="runId")
    experiment_id: str | None = Field(default=None, alias="experimentId")
    payload: dict[str, Any] = Field(default_factory=dict)


class SourceSnapshot(ApiContract):
    snapshot_id: str = Field(alias="snapshotId")
    source_digest: str = Field(alias="sourceDigest", pattern=r"^[0-9a-fA-F]{64}$")
    config_digest: str = Field(alias="configDigest", pattern=r"^[0-9a-fA-F]{64}$")
    environment: dict[str, Any] = Field(default_factory=dict)
    source_files: list[ArtifactRef] = Field(default_factory=list, alias="sourceFiles")
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    origin_run_id: str = Field(alias="originRunId")
    created_at: str = Field(alias="createdAt")


class ExecutionSpec(ApiContract):
    owner_id: str = Field(alias="ownerId")
    dimension: Literal[2, 3]
    solver_profile: Literal["standard", "verify"] = Field(alias="solverProfile")
    backend: Literal["local-matlab", "compiled-runtime", "MATLAB_MCP"]
    parameters: dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(ApiContract):
    evaluated: bool
    feasible: bool | None = None
    status: str
    metrics: dict[str, float | int | None] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list, alias="evidenceIds")


class RunArtifact(ApiContract):
    run_id: str = Field(alias="runId")
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    config_digest: str = Field(alias="configDigest", pattern=r"^[0-9a-fA-F]{64}$")
    files: list[ArtifactRef] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    evaluation: EvaluationResult | None = None


class PromotionRequest(ApiContract):
    name: str = Field(default="快速实现基线研究", min_length=1, max_length=120)
    goal: str = Field(default="以不可变快速实现快照为基线开展深度优化", min_length=1, max_length=2000)
    # Keep the public request field in its wire-format spelling.  FastAPI wraps
    # body models in ``Annotated`` metadata and some Pydantic/FastAPI version
    # combinations treat a nested ``Field(alias=...)`` as unsupported metadata.
    budgetTotal: int = Field(default=12, ge=1, le=10000)


class PromotionResult(ApiContract):
    research_id: str = Field(alias="researchId")
    snapshot: SourceSnapshot
    research: dict[str, Any]
