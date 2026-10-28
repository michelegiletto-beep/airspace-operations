# 0.2 publication authoring handover

These are prepared publication sources. They do not themselves establish upload, publication or independent retrieval. `status.json` still records the frozen 0.1 publication; the release owner updates the new publication record after actual delivery.

Website mapping in the existing System Labs checkout:

| Prepared source | Existing-site destination |
| --- | --- |
| `site-project.html` | `public/projects/airspace-operations.html` |
| `site-project.css` | `public/assets/airspace-project.css` |
| `media/*` | `public/airspace-operations/media/*` |

The HTML retains the site's `/assets/lab.css` identity and links to the existing multiagentic-systems dossier. It does not require a new Site, replace the homepage or publish an operational tenant. No native publication or real-site/workroot modification was performed by this authoring task.

Seven actual application JPEGs are supplied by the release owner: `mission-control`, `airspace-planning`, `fleet-maintenance`, `european-coordination`, `scheduling`, `agent-orchestration` and `agent-orchestration-detail`. All are present. There are no generated screen placeholders. The root release step refreshes final captures and verifies their references before publication. The accompanying SVG is authored from the actual control path. Indigo and Coral are byte-identical authorised owner assets; their separate rights remain recorded in `frontend/public/mascots/RIGHTS.md` and `provenance.json`.

The new download is deliberately disabled and labelled **Prepared**. After verification, replace that button with a real download link to the verified 0.2 ZIP, update the release-state text and add final artifact checksums/clean-install evidence. Do not infer publication from `data-prepared-url`. The old 0.1 ZIP and tag remain unchanged; its checksum link points to the frozen GitHub release asset so a new top-level checksum file cannot change its meaning.

`github-readme-v2.md` targets the repository-root `README.md`; its screenshot paths are relative to that destination. The two HF card drafts target each Hub repository's root `README.md`; upload `media/agent-orchestration.jpg` and `media/orchestration-pipeline.svg` beside each card. The cards explicitly preserve the unchanged student/dataset lineage and do not claim new weights, new training, a hosted inference service or a production Space. The five owner-authorised 2.5D WebGL resources are identified by actual hashes; the cards do not assert a synchronously verified source package version.

`hf-space/` is a separate self-contained **static** evaluation viewer. Its official `sdk: static` README metadata targets a Space root. Publish the directory contents, not the full application or model cache. It contains four unchanged source reports, a derived evidence index with source-linked failure examples, seven screenshots and the architecture SVG. It executes no inference and includes no reserved renderer modules, original companion PNGs, model weights or operational data. New downloads remain Prepared. The actual reports retain their original timestamps; the 204.91-second first experiment is separate from the later UI trace's 305.794-second span.

After the final screenshot refresh, run these commands from the product directory:

```powershell
.venv/Scripts/python.exe publication/hf-space/prepare.py
.venv/Scripts/python.exe publication/verify-publication.py
node publication/verify-publication.mjs
```

The preparation helper refuses missing evidence/media and updates raw-report/media SHA-256 provenance. The two checks cover HTML IDs and local references, CSS/JavaScript syntax, SVG/image decoding, raw-copy checksums, all workspace/trace/view controls, keyboard selection, missing-data behaviour, source-text injection escaping and disabled Prepared downloads. These are local authoring checks, not a browser-rendering, clean-install or public-delivery claim. Root publication verifies the final destination and records the verified URL.
