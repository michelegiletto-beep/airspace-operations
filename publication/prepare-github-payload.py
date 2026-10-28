"""Prepare versioned source-tree payloads; this script performs no upload."""
import argparse
from pathlib import Path
import gzip
import json
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from package_release import source_files, SECRET_PATTERNS
from release_support import current_version, github_payload_directory


def prepare_payload(root=ROOT, *, legacy_output=False):
    version = current_version(root)
    out = github_payload_directory(root, version, legacy=legacy_output)
    out.mkdir(parents=True, exist_ok=True)
    files, experiments = [], []
    for file, rel in source_files():
        data = file.read_bytes()
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            raise SystemExit("Potential credential pattern: " + rel.as_posix())
        if rel.as_posix() == "sources/corpus.json":
            target = out / "corpus.json.gz"
            with gzip.GzipFile(filename=str(target), mode="wb", mtime=0) as stream:
                stream.write(data)
            files.append({"path": "sources/corpus.json.gz", "local_path": str(target), "bytes": target.stat().st_size, "binary": True})
        elif rel.parts[:2] == ("models", "runs") and file.stat().st_size > 100000:
            experiments.append((file, rel))
        else:
            files.append({"path": rel.as_posix(), "local_path": str(file), "bytes": len(data), "binary": file.suffix.lower() in {".safetensors", ".png", ".jpg", ".jpeg", ".webp", ".zip", ".gz", ".ico", ".woff", ".woff2"} or b"\x00" in data[:8192]})
    bundle = out / "experiment-artifacts.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file, rel in experiments:
            archive.write(file, Path(*rel.parts[1:]).as_posix())
    files.append({"path": "models/experiment-artifacts.zip", "local_path": str(bundle), "bytes": bundle.stat().st_size, "binary": True})
    small, large = [], []
    for entry in files:
        if entry["binary"] or entry["bytes"] > 100000:
            large.append(entry)
        else:
            small.append({"path": entry["path"], "mode": "100644", "type": "blob", "content": Path(entry["local_path"]).read_text(encoding="utf-8", newline="")})
    batches, batch, size = [], [], 0
    for item in small:
        if batch and size + len(item["content"]) > 150000:
            batches.append(batch)
            batch, size = [], 0
        batch.append(item)
        size += len(item["content"])
    if batch:
        batches.append(batch)
    batch_paths = []
    for index, batch in enumerate(batches):
        destination = out / f"tree-{index:02d}.json"
        destination.write_text(json.dumps(batch, ensure_ascii=True), encoding="utf-8")
        batch_paths.append(str(destination))
    large_path = out / "large.json"
    large_path.write_text(json.dumps(large, indent=2), encoding="utf-8")
    inventory = {"version": version, "state": "Prepared", "publication_performed": False,
                 "output_directory": str(out), "legacy_output": legacy_output,
                 "files": len(files), "batches": len(batches), "batch_paths": batch_paths,
                 "small_batches": len(batches),
                 "large_files": [{key: value for key, value in entry.items() if key != "local_path"} for entry in large],
                 "large_path": str(large_path), "large": large}
    inventory_path = out / "inventory.json"
    inventory["inventory_path"] = str(inventory_path)
    inventory_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-output", action="store_true", help="Use the previous unversioned runtime/publication/github directory for older consumers")
    args = parser.parse_args()
    inventory = prepare_payload(legacy_output=args.legacy_output)
    print(json.dumps({key: value for key, value in inventory.items() if key != "large"}, indent=2))


if __name__ == "__main__":
    main()
