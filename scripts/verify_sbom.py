"""Validate the SBOM against the official CycloneDX 1.6 JSON schema."""
import hashlib
import importlib.metadata
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_URL = "https://cyclonedx.org/schema/bom-1.6.schema.json"
SCHEMA_REVISION = "e833d732337dd33aceb45ff1991f896796f1e5e7"
observed = {}


def retrieve(url):
    parts = urlsplit(url)
    if parts.hostname != "cyclonedx.org" or not parts.path.startswith("/schema/"):
        raise ValueError("Schema retrieval is restricted to the official CycloneDX schema directory")
    # The canonical website returned HTTP 403 in this environment. Use the
    # same standard from its official, pinned specification repository.
    url = "https://raw.githubusercontent.com/CycloneDX/specification/" + SCHEMA_REVISION + "/schema/" + Path(parts.path).name
    with urllib.request.urlopen(url, timeout=20) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("Schema exceeds the validation size bound")
    observed[url] = hashlib.sha256(data).hexdigest()
    return json.loads(data)


schema = retrieve(SCHEMA_URL)
data = (ROOT / "SBOM.cdx.json").read_bytes()
document = json.loads(data)
resolver = jsonschema.RefResolver.from_schema(schema, handlers={"http": retrieve, "https": retrieve})
jsonschema.Draft7Validator(schema, resolver=resolver).validate(document)
report = {"checked_at": datetime.now(timezone.utc).isoformat(), "valid": True,
          "sbom_sha256": hashlib.sha256(data).hexdigest(), "components": len(document["components"]),
          "validator": "jsonschema " + importlib.metadata.version("jsonschema"),
          "official_schema_sha256": observed,
          "scope": "CycloneDX JSON format validation; not a licence clearance or vulnerability assessment"}
version = document["metadata"]["component"]["version"]
destination = ROOT / "release-evidence" / ("v" + version) / "sbom-validation.json"
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
