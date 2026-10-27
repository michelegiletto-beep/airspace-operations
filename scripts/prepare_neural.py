"""Explicitly download reviewed, Apache-2.0 pretrained local model files.

Uses public Hub downloads, not a hosted inference API. No remote Python code or
pickle weights are accepted. Repository revisions and file checksums are saved.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from airspace.neural import MODEL_REGISTER


def main():
    from huggingface_hub import HfApi, snapshot_download
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", action="append", choices=list(MODEL_REGISTER))
    parser.add_argument("--output", type=Path, default=ROOT / "models" / "pretrained")
    parser.add_argument("--refresh",action="store_true",help="Explicitly resolve the current upstream revision instead of the reviewed pinned revision")
    args = parser.parse_args()
    for name in args.component or ["encoder", "reranker", "teacher"]:
        item = MODEL_REGISTER[name]
        info = HfApi().model_info(item["repository"],revision=None if args.refresh else item["revision"])
        licence = (info.card_data or {}).get("license")
        if licence != "apache-2.0":
            raise ValueError(f"{name}: current Hub licence is not the reviewed Apache-2.0 licence")
        folder = args.output / name
        snapshot_download(item["repository"], revision=info.sha, local_dir=folder,
                          allow_patterns=["config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "spiece.model", "vocab.txt", "added_tokens.json", "generation_config.json", "README.md", "LICENSE", "LICENSE.txt"],
                          max_workers=2)
        files = {str(p.relative_to(folder)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in folder.rglob("*") if p.is_file() and ".cache" not in p.parts and p.name!="provenance.json"}
        record = {**item, "revision": info.sha, "reviewed_pin":item["revision"],"explicit_refresh":args.refresh,"retrieved_at": datetime.now(timezone.utc).isoformat(),
                  "download_mode": "Explicit public model file download; no hosted inference", "files": files,
                  "remote_code": False, "weight_serialisation": "safetensors", "review_status": "Upstream licence metadata checked; experimental downstream use"}
        (folder / "provenance.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(json.dumps({"component": name, "revision": info.sha, "files": len(files), "bytes": sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())}), flush=True)


if __name__ == "__main__":
    main()
