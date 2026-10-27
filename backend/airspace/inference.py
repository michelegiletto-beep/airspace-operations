"""Separately runnable, authenticated local experimental inference worker."""
import hashlib
import os
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .identity import authenticate
from .neural import LocalEncoder, ExperimentalStudent
from .storage import local_store


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texts: list[str] = Field(min_length=1, max_length=32)


def create_inference_app(store=None):
    store = store or local_store()
    store.migrate()
    app = FastAPI(title="Airspace Operations experimental local inference", version="0.1.0-rc.1")
    loaded = []

    @app.get("/health")
    def health():
        return {"status": "ok", "model_loaded": bool(loaded), "operational_decisions_permitted": False}

    @app.post("/v1/classify")
    def classify(payload: Classification, authorization: str = Header()):
        token = authorization[7:] if authorization.startswith("Bearer ") else None
        user = authenticate(store, token)
        if any(len(text) > 8000 for text in payload.texts):
            raise HTTPException(422, "Passages must contain at most 8000 characters")
        folder = os.environ.get("AIRSPACE_STUDENT_PATH")
        encoder_folder = os.environ.get("AIRSPACE_ENCODER_PATH")
        if not folder or not encoder_folder:
            raise HTTPException(503, "Explicit local model paths are required")
        if not loaded:
            try:
                loaded.append(ExperimentalStudent(Path(folder), LocalEncoder(Path(encoder_folder))))
            except (ValueError, OSError, ImportError):
                raise HTTPException(503, "Reviewed local model files are unavailable")
        result = loaded[0].classify(payload.texts)
        with store.engine.begin() as conn:
            store.append_audit(conn, user["organisation_id"], user["id"], "model.classified", {"model_version": loaded[0].version, "input_sha256": [hashlib.sha256(t.encode()).hexdigest() for t in payload.texts], "count": len(payload.texts), "promotion": "Experimental; no operational decision"})
        return {"items": result, "task": "Explicit shall-language reviewer routing", "human_validated": False, "legal_interpretation": False}
    return app
