"""Explicitly download the pinned, public local orchestration model; no remote code."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
MODEL = "Qwen/Qwen3-1.7B"
REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"


def main():
    target = ROOT / "models/pretrained/controller"
    snapshot_download(MODEL, revision=REVISION, local_dir=target,
                      allow_patterns=["*.json", "*.safetensors", "merges.txt", "README.md", "LICENSE"],
                      token=False, max_workers=2)
    files = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.file_digest(p.open("rb"), "sha256").hexdigest()}
             for p in target.iterdir() if p.is_file() and p.name != "provenance.json"}
    manifest = {"model_id": MODEL, "repository": MODEL, "revision": REVISION, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "licence": "Apache-2.0; upstream LICENSE applies", "source": "https://huggingface.co/" + MODEL,
                "remote_code_execution": False, "files": files,
                "scope": "Pretrained orchestration controller, not a custom-trained System Lab foundation model. No operational reliability claim."}
    (target / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"model_id": MODEL, "revision": REVISION, "files": len(files), "bytes": sum(x["bytes"] for x in files.values())}))


if __name__ == "__main__":
    main()
