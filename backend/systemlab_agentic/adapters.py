"""A small second domain adapter proving neutral core reuse without UAS types."""
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4
from .contracts import TaskContract, Artifact, ActionReceipt
from .core import admit


class DocumentResearchAdapter:
    """Read-only exact-source research; documents are supplied by its host app."""
    domain = "document_research"

    def __init__(self, documents: list[dict]):
        self.documents=documents

    def execute(self, task: TaskContract, query: str, *, actor_id: str, organisation_id: str):
        capability="document.find_sources"
        decision=admit(task,capability,actor_id=actor_id,organisation_id=organisation_id,observed_snapshot=task.scope.context_snapshot,
                       completed=set(),steps_used=0,model_calls_used=0)
        if not decision["allowed"]:raise PermissionError("; ".join(decision["reasons"]))
        words=set(query.lower().split())
        matches=[]
        for document in self.documents:
            if document.get("organisation_id") not in (None,organisation_id):continue
            if not words & set(document["text"].lower().split()):continue
            actual=hashlib.sha256(document["text"].encode()).hexdigest()
            if document["checksum"]!=actual:raise ValueError("Document integrity failed")
            matches.append({"id":document["id"],"quotation":document["text"],"source_uri":document["source_uri"],"checksum":actual})
        payload={"citations":matches,"conclusion":None,"review_required":True}
        output=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        artifact=Artifact(id=str(uuid4()),kind="document_research",capability_id=capability,payload=payload,
                          provenance={"actor_id":actor_id,"organisation_id":organisation_id,"context_snapshot":task.scope.context_snapshot,"output_checksum":output})
        receipt=ActionReceipt(id=str(uuid4()),task_id=task.id,capability_id=capability,scope_id=task.scope.scope_id,state="Completed",input_snapshot=task.scope.context_snapshot,
                              observed_snapshot=task.scope.context_snapshot,artifact_id=artifact.id,actor_id=actor_id,at=datetime.now(timezone.utc))
        return artifact,receipt
