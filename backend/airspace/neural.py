"""Local pretrained retrieval and experimental trained student inference.

No remote code, online learning, external model API, or operational decision
authority is enabled here. Model files must be present locally and reviewed.
"""
from __future__ import annotations
import hashlib
import json
import os
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
import re
from threading import RLock

MODEL_REGISTER = {
    "encoder": {"repository": "sentence-transformers/all-MiniLM-L6-v2", "revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41", "licence": "Apache-2.0", "max_tokens": 256},
    "reranker": {"repository": "cross-encoder/ms-marco-MiniLM-L6-v2", "revision": "233902d25c440f23af6f7d6e94d2946bac0bee0a", "licence": "Apache-2.0", "max_tokens": 256},
    "teacher": {"repository": "google/flan-t5-small", "revision": "0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab", "licence": "Apache-2.0", "max_tokens": 512},
    "teacher-base": {"repository": "google/flan-t5-base", "revision": "7bcac572ce56db69c1ea7c8af255c5d7c9672fc2", "licence": "Apache-2.0", "max_tokens": 512},
}
LABELS = ["no_explicit_shall", "explicit_shall"]
PROMPT_VERSION = "explicit-shall-routing-3"
TEACHER_PROMPT = (
    "Text: {text}\nDoes this text contain the word shall? Answer yes or no."
)
MODAL = re.compile(r"\bshall\b", re.I)


def _load_transformers(path, cls):
    from transformers import AutoTokenizer
    path = Path(path)
    if not path.is_dir():
        raise FileNotFoundError("Reviewed local model directory is missing; run scripts/prepare_neural.py")
    tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)
    model = cls.from_pretrained(str(path), local_files_only=True, trust_remote_code=False, use_safetensors=True)
    model.eval()
    return tokenizer, model


class LocalEncoder:
    def __init__(self, path, device="cpu"):
        if not Path(path).is_dir():
            raise FileNotFoundError("Reviewed local encoder is missing")
        from transformers import AutoModel
        import torch
        self.tokenizer, self.model = _load_transformers(path, AutoModel)
        self.model.to(device)
        self.device = device
        provenance = Path(path) / "provenance.json"
        self.version = (json.loads(provenance.read_text(encoding="utf-8")).get("repository", "local") + "@" + json.loads(provenance.read_text(encoding="utf-8")).get("revision", "unregistered")) if provenance.exists() else "Unregistered local encoder"
        torch.set_num_threads(min(4, torch.get_num_threads()))

    def encode(self, texts: list[str], batch_size=16):
        import torch
        vectors = []
        with torch.inference_mode():
            for start in range(0, len(texts), batch_size):
                tokens = self.tokenizer(texts[start:start + batch_size], return_tensors="pt", padding=True, truncation=True, max_length=256).to(self.device)
                output = self.model(**tokens).last_hidden_state
                mask = tokens["attention_mask"].unsqueeze(-1)
                means = (output * mask).sum(1) / mask.sum(1).clamp(min=1)
                means = torch.nn.functional.normalize(means, p=2, dim=1)
                vectors.extend(means.cpu().tolist())
        return vectors


class LocalReranker:
    def __init__(self, path, device="cpu"):
        if not Path(path).is_dir():
            raise FileNotFoundError("Reviewed local reranker is missing")
        from transformers import AutoModelForSequenceClassification
        self.tokenizer, self.model = _load_transformers(path, AutoModelForSequenceClassification)
        self.model.to(device)
        self.device = device
        provenance = Path(path)/"provenance.json"
        info = json.loads(provenance.read_text(encoding="utf-8")) if provenance.exists() else {}
        self.version = info.get("repository","Unregistered local reranker") + "@" + info.get("revision","unregistered")

    def rank(self, query: str, passages: list[str]):
        import torch
        scores = []
        with torch.inference_mode():
            for start in range(0, len(passages), 16):
                batch = passages[start:start + 16]
                tokens = self.tokenizer([query] * len(batch), batch, return_tensors="pt", padding=True, truncation=True, max_length=256).to(self.device)
                scores.extend(self.model(**tokens).logits.flatten().cpu().tolist())
        return scores


class LocalTeacher:
    def __init__(self, path, device="cpu"):
        if not Path(path).is_dir():
            raise FileNotFoundError("Reviewed local teacher is missing")
        from transformers import AutoModelForSeq2SeqLM
        self.tokenizer, self.model = _load_transformers(path, AutoModelForSeq2SeqLM)
        self.model.to(device)
        self.device = device
        provenance = Path(path) / "provenance.json"
        info = json.loads(provenance.read_text(encoding="utf-8")) if provenance.exists() else {}
        self.version = info.get("repository","Unregistered local teacher") + "@" + info.get("revision","unregistered")

    def annotate(self, passages: list[dict], batch_size=8):
        import torch
        output = []
        for start in range(0, len(passages), batch_size):
            batch = passages[start:start + batch_size]
            prompts = [TEACHER_PROMPT.format(text=p["text"]) for p in batch]
            tokens = self.tokenizer(prompts, return_tensors="pt", padding=True, truncation=True, max_length=512).to(self.device)
            with torch.inference_mode():
                generated = self.model.generate(**tokens, do_sample=False, max_new_tokens=6)
            labels = self.tokenizer.batch_decode(generated, skip_special_tokens=True)
            for passage, prompt, raw in zip(batch, prompts, labels):
                output.append(validate_annotation(passage, raw, self.version, hashlib.sha256(prompt.encode()).hexdigest()))
        return output


def validate_annotation(passage: dict, raw: str, teacher: str, prompt_checksum: str) -> dict:
    normal = raw.strip().lower().strip(". ")
    label = {"yes": LABELS[1], "no": LABELS[0], LABELS[1]: LABELS[1], LABELS[0]: LABELS[0]}.get(normal)
    matches = list(MODAL.finditer(passage["text"]))
    reasons = []
    if label is None:
        reasons.append("Teacher output is outside the schema")
    if label == LABELS[1] and not matches:
        reasons.append("Explicit-shall label has no exact source-span support")
    if label == LABELS[0] and matches:
        reasons.append("Unmarked label contradicts an explicit shall marker; review required")
    return {"passage_id": passage["id"], "source_id": passage["source_id"],
            "source_checksum": passage["source_checksum"], "document_version": passage["document_version"],
            "text_checksum": hashlib.sha256(passage["text"].encode()).hexdigest(),
            "source_spans": [{"start": m.start(), "end": m.end(), "text": m.group()} for m in matches],
            "label": label, "teacher": teacher, "teacher_raw_output": raw,
            "prompt_version": PROMPT_VERSION, "prompt_checksum": prompt_checksum,
            "output_schema": "explicit-shall-binary-3 (yes/no mapped to explicit_shall/no_explicit_shall)", "validation_results": reasons,
            "status": "Quarantined" if reasons else "Machine-generated — Unreviewed",
            "human_reviewed": False, "ground_truth": False}


def make_student(input_size=384, hidden_size=32):
    import torch
    return torch.nn.Sequential(torch.nn.Linear(input_size, hidden_size), torch.nn.ReLU(), torch.nn.Linear(hidden_size, 2))


class ExperimentalStudent:
    def __init__(self, path, encoder: LocalEncoder):
        from safetensors.torch import load_file
        folder = Path(path)
        self.card = json.loads((folder / "run.json").read_text(encoding="utf-8"))
        if self.card.get("promotion_status") != "Experimental — Not promoted":
            raise ValueError("Unexpected or unreviewed model promotion metadata")
        self.model = make_student(self.card["architecture"]["input_size"], self.card["architecture"]["hidden_size"])
        self.model.load_state_dict(load_file(str(folder / "student.safetensors")))
        self.model.eval()
        self.encoder = encoder
        self.version = self.card["run_id"]

    def classify(self, texts: list[str]):
        import torch
        vectors = torch.tensor(self.encoder.encode(texts), dtype=torch.float32)
        with torch.inference_mode():
            probabilities = torch.softmax(self.model(vectors), dim=1)
        return [{"label": LABELS[int(row.argmax())], "model_probability": float(row.max()),
                 "probability_meaning": "Uncalibrated classifier output; not legal confidence",
                 "model_version": self.version, "status": "Experimental — requires reviewer validation",
                 "operational_decision_permitted": False} for row in probabilities]


_MODEL_LOCK = RLock()
_EMBEDDINGS: OrderedDict = OrderedDict()
_EMBEDDING_LIMIT = 16384


class ScopedCachedEncoder:
    """A bounded cache whose keys include the organisation scope.

    Callers still filter documents before calling encode. Raw documents and
    questions are never retained in the cache. Cache entries cannot be queried
    through an API; identical text in another tenant uses a distinct key.
    """
    def __init__(self, encoder, organisation_id):
        self.encoder, self.scope, self.version = encoder, organisation_id or "public-only", encoder.version

    def encode(self, texts):
        keys = [(self.scope, hashlib.sha256(t.encode()).hexdigest()) for t in texts]
        with _MODEL_LOCK:
            missing = list(dict.fromkeys(i for i,k in enumerate(keys) if k not in _EMBEDDINGS))
            # Model inference is serialized to bound concurrent CPU/RAM usage.
            if missing:
                vectors = self.encoder.encode([texts[i] for i in missing])
                for i, vector in zip(missing,vectors):
                    _EMBEDDINGS[keys[i]] = vector
            result = [_EMBEDDINGS[k] for k in keys]
            for key in keys:
                _EMBEDDINGS.move_to_end(key)
            while len(_EMBEDDINGS) > _EMBEDDING_LIMIT:
                _EMBEDDINGS.popitem(last=False)
            return result


@lru_cache(maxsize=2)
def _local_models(path: str, device: str):
    return LocalEncoder(Path(path)/"encoder", device), LocalReranker(Path(path)/"reranker",device)


def configure_local_retrieval(organisation_id: str | None = None) -> dict:
    """Return source_answer kwargs only when local neural retrieval is enabled.

    AIRSPACE_NEURAL_RETRIEVAL=local and explicitly downloaded, pinned model files
    are required. Missing models raise a visible error for the API to record;
    retrieval can then continue using its lexical-only degraded path.
    """
    if os.environ.get("AIRSPACE_NEURAL_RETRIEVAL", "disabled") != "local":
        return {}
    default = Path(__file__).resolve().parents[2]/"models"/"pretrained"
    model_dir = os.environ.get("AIRSPACE_MODEL_DIR", str(default))
    device = os.environ.get("AIRSPACE_INFERENCE_DEVICE", "cpu")
    if device not in {"cpu", "cuda"}:
        raise ValueError("Local inference device must be cpu or cuda")
    encoder, reranker = _local_models(model_dir,device)
    return {"encoder": ScopedCachedEncoder(encoder,organisation_id), "reranker":reranker}
