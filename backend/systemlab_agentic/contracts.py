"""Contracts shared by domain adapters; no trading or aviation assumptions."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AgentBudget(Contract):
    max_steps: int = Field(default=8, ge=1, le=16)
    max_model_calls: int = Field(default=8, ge=0, le=16)
    max_wall_seconds: int = Field(default=900, ge=1, le=3600)
    model_timeout_seconds: int = Field(default=90, ge=1, le=300)
    tool_timeout_seconds: int = Field(default=120, ge=1, le=300)
    max_retries: int = Field(default=1, ge=0, le=2)


class AgentScope(Contract):
    scope_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    organisation_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    actor_role: str = Field(min_length=1)
    record_versions: dict[str, int]
    context_snapshot: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: AwareDatetime
    deadline: AwareDatetime


class Capability(Contract):
    id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    effect: Literal["read_only", "internal_draft", "external_action"]
    required_roles: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    input_contract: str
    output_contract: str
    independent_review_required: bool = True


class TaskContract(Contract):
    id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    scope: AgentScope
    capabilities: list[Capability]
    budget: AgentBudget
    external_action_approvals: list[str] = Field(default_factory=list)


class Artifact(Contract):
    id: str
    kind: str
    capability_id: str
    payload: dict
    provenance: dict
    review_required: bool = True


class ActionReceipt(Contract):
    id: str
    task_id: str
    capability_id: str
    scope_id: str
    state: Literal["Proposed", "Started", "Completed", "Failed", "Cancelled", "Unknown"]
    input_snapshot: str
    observed_snapshot: str | None = None
    artifact_id: str | None = None
    actor_id: str
    at: AwareDatetime
    external_request_id: str | None = None
    confirmed_external_outcome: bool = False


class WaitPolicy(Contract):
    deadline: AwareDatetime
    max_attempts: int = Field(default=2, ge=1, le=5)
    poll_interval_seconds: float = Field(default=1, ge=0.1, le=30)
    on_expiry: Literal["defer", "fail", "reconcile"] = "reconcile"
