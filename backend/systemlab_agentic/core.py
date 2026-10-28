"""Deterministic scope, resource, receipt and recovery admission."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from .contracts import TaskContract, ActionReceipt, Artifact, WaitPolicy


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()


def admit(task: TaskContract, capability_id: str, *, actor_id: str, organisation_id: str, observed_snapshot: str,
          completed: set[str], steps_used: int, model_calls_used: int, at: datetime | None = None) -> dict:
    at=at or datetime.now(timezone.utc)
    reasons=[]
    capabilities=[c for c in task.capabilities if c.id==capability_id]
    if actor_id!=task.scope.actor_id or organisation_id!=task.scope.organisation_id:
        reasons.append("Actor or organisation does not match the admitted scope")
    if observed_snapshot!=task.scope.context_snapshot:
        reasons.append("Observed context differs from the task's input snapshot")
    if at>=task.scope.deadline:
        reasons.append("Task deadline has expired")
    if steps_used>=task.budget.max_steps or model_calls_used>task.budget.max_model_calls:
        reasons.append("Declared resource budget is exhausted")
    if len(capabilities)!=1:
        reasons.append("Capability is not uniquely admitted by this task")
    else:
        capability=capabilities[0]
        if capability.domain not in {task.scope.domain,"shared"}:
            reasons.append("Capability belongs to a different domain adapter")
        if capability.required_roles and task.scope.actor_role not in capability.required_roles:
            reasons.append("Actor role is not admitted for this capability")
        if not set(capability.prerequisites)<=completed:
            reasons.append("Capability dependencies do not have completed receipts")
        if capability.effect=="external_action" and capability.id not in task.external_action_approvals:
            reasons.append("External action lacks an independently recorded scoped approval")
    return {"allowed":not reasons,"reasons":reasons,"task_id":task.id,"scope_id":task.scope.scope_id,"capability_id":capability_id,"rule_version":"systemlab-agentic-admission/1.0"}


def verify_artifact(artifact: Artifact, scope) -> dict:
    reasons=[]
    provenance=artifact.provenance
    if provenance.get("organisation_id")!=scope.organisation_id or provenance.get("actor_id")!=scope.actor_id:
        reasons.append("Artifact actor or organisation differs from its task scope")
    if provenance.get("context_snapshot")!=scope.context_snapshot:
        reasons.append("Artifact context snapshot is incompatible")
    if provenance.get("output_checksum")!=_digest(artifact.payload):
        reasons.append("Artifact content does not match its recorded checksum")
    return {"valid":not reasons,"reasons":reasons,"artifact_id":artifact.id}


def reconcile(expected_snapshot: str, observed_snapshot: str, receipt: ActionReceipt | None, *, external_effect_possible: bool) -> dict:
    if expected_snapshot!=observed_snapshot:
        return {"state":"Reconciliation Required","may_continue":False,"reason":"Scoped observations changed"}
    if receipt is not None and receipt.state=="Completed":
        if external_effect_possible and not receipt.confirmed_external_outcome:
            return {"state":"Reconciliation Required","may_continue":False,"reason":"A request receipt is not confirmation of external outcome"}
        return {"state":"Confirmed","may_continue":True,"reason":"Compatible completed receipt"}
    if external_effect_possible:
        return {"state":"Reconciliation Required","may_continue":False,"reason":"Uncertain external outcome must not be blindly retried"}
    return {"state":"Retry Read-only Work","may_continue":True,"reason":"No external mutation capability; bounded read-only retry is permitted"}


def wait_decision(policy: WaitPolicy, *, attempts: int, at: datetime | None = None, cancelled=False, paused=False) -> dict:
    at=at or datetime.now(timezone.utc)
    if cancelled:return {"state":"Cancelled","continue":False,"compute_released":False}
    if paused:return {"state":"Paused","continue":False,"compute_released":False}
    if at>=policy.deadline or attempts>=policy.max_attempts:
        return {"state":policy.on_expiry,"continue":False,"compute_released":False}
    return {"state":"Wait","continue":True,"poll_interval_seconds":policy.poll_interval_seconds,"compute_released":False}
