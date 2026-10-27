"""Local-only inference for the experimental shall-language routing student."""
import hashlib
import json
from pathlib import Path


def classify(texts, encoder_path, model_path=None):
    import torch
    from safetensors.torch import load_file
    from transformers import AutoModel, AutoTokenizer
    folder = Path(model_path or Path(__file__).resolve().parent)
    encoder_path = Path(encoder_path)
    if not encoder_path.is_dir():
        raise ValueError("Supply the reviewed local encoder directory; no implicit download occurs")
    if not 1 <= len(texts) <= 32 or any(not isinstance(t, str) or len(t) > 8000 for t in texts):
        raise ValueError("Supply between1 and32 source passages, each at most8000 characters")
    card = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    weights = folder / "student.safetensors"
    if hashlib.sha256(weights.read_bytes()).hexdigest() != card["artifact_checksum"]:
        raise ValueError("Student weight integrity failed")
    architecture = card["architecture"]
    student = torch.nn.Sequential(torch.nn.Linear(architecture["input_size"], architecture["hidden_size"]), torch.nn.ReLU(), torch.nn.Linear(architecture["hidden_size"], 2))
    student.load_state_dict(load_file(str(weights)))
    student.eval()
    torch.set_num_threads(min(4, torch.get_num_threads()))
    tokenizer = AutoTokenizer.from_pretrained(str(encoder_path), local_files_only=True, trust_remote_code=False)
    encoder = AutoModel.from_pretrained(str(encoder_path), local_files_only=True, trust_remote_code=False, use_safetensors=True)
    encoder.eval()
    with torch.inference_mode():
        tokens = tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=256)
        hidden = encoder(**tokens).last_hidden_state
        mask = tokens["attention_mask"].unsqueeze(-1)
        vectors = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
        probabilities = torch.softmax(student(torch.nn.functional.normalize(vectors, p=2, dim=1)), dim=1)
    return [{"label": architecture["outputs"][int(row.argmax())], "model_probability": float(row.max()), "meaning": "Uncalibrated literal-language routing output; no legal or operational confidence", "model_version": card["run_id"], "promotion": "Experimental — Not promoted"} for row in probabilities]
