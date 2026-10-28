"""Read existing public project copy. No authentication, mutation or deployment."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {
    "system-lab": "https://giletto-systems-lab.michele-giletto.chatgpt.site/projects/airspace-operations",
    "hf-model": "https://huggingface.co/Magic51/system-lab-airspace-shall-router/resolve/main/README.md",
    "hf-dataset": "https://huggingface.co/datasets/Magic51/system-lab-airspace-source-annotations/resolve/main/README.md",
    "hf-space": "https://magic51-system-lab-airspace-evaluation.static.hf.space/",
}


def read_one(item):
    name, url = item
    result = {"name": name, "url": url, "checked_at": datetime.now(timezone.utc).isoformat()}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "SystemLab-PublicCopyReview/0.3"}), timeout=20) as response:
            content = response.read(2_000_001)
            if len(content) > 2_000_000:
                raise ValueError("Source exceeds review bound")
            target = ROOT / "runtime/publication/v0.3/public-copy" / (name + ".txt")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            result.update(status=response.status, final_url=response.url, bytes=len(content),
                          sha256=hashlib.sha256(content).hexdigest(), private_local_capture=str(target.relative_to(ROOT)),
                          result="Read")
    except Exception as error:
        result.update(result="Unavailable", failure_type=type(error).__name__)
    return result


def main():
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(read_one, TARGETS.items()))
    report = {"purpose": "Actual existing public-source copy review for a prepared revision", "publication_performed": False,
              "prior_web_tool_attempt": "The web opener returned Internal Error for all four URLs; bounded unauthenticated HTTPS reads were attempted next", "sources": results}
    (Path(__file__).parent / "public-source-audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
