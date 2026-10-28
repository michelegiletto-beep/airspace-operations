---
title: System Lab Airspace Evaluation
sdk: static
app_file: index.html
colorFrom: indigo
colorTo: gray
license: apache-2.0
short_description: Recorded agent and neural evidence; no live flights.
---

# System Lab Airspace Evaluation

This self-contained static Space lets readers inspect **recorded software evidence** from System Lab Airspace Operations. It does not run a model, accept uploads, connect to an operational tenant, contact anyone or manage aircraft. No flight history, customer, telemetry or authorisation has been fabricated.

The bundled evidence contains:

- Four actual native/local-causal runs over two developer-authored, source-grounded research queries. All four ended at Needs Review. Run order and cache reuse confound elapsed times; no speed or legal-quality superiority is claimed.
- The actual authenticated UI-and-worker research workflow, with five Qwen/neural steps, 12 supporting passages, model versions, source anchors and the preserved independent-review gate.
- A separate first causal-controller experiment. Its 204.91-second duration is not substituted for the different UI workflow's timestamps.
- The unchanged experimental student's original evaluation and source-linked failure examples. No new weights, training or human ground truth are claimed.
- Actual application screenshots and a code-native diagram of the scoped control path.

The main application's local Qwen controller, pretrained retrieval/reranking, deterministic operational specialists and new reusable `systemlab_agentic` core are separate from this static viewer. Its owner-authorised 2.5D WebGL presentation resources are UI assets, not neural inference or permission logic. The reserved renderer is not executed or redistributed in this Space; screenshots and an identity summary document its application role.

Download links are enabled only after the release owner verifies the actual published assets. The verified current candidate is recorded below. This Space is an evaluation-documentation interface, not the production operations platform, a hosted inference endpoint or aviation acceptance evidence.

## Provenance and rights

Raw reports are under `data/`; `data/provenance.json` records source paths and SHA-256 checksums. Report bytes are copied unchanged from the project evidence. The compact index is derived from those records, not generated observations.

Source attribution: European Union Aviation Safety Agency, Easy Access Rules; copyright EASA 2003–2026. EU legal documents: copyright European Union 1998–2026. Source-specific rights and acknowledged-reproduction conditions remain separate from the newly authored viewer code's Apache-2.0 licence. Screenshots containing the owner's companion artwork retain the separate rights stated in `NOTICE.md`.

## Prepare and preview

From the full Airspace source checkout, run `python publication/hf-space/prepare.py` after refreshing the final screenshots. It refuses missing actual evidence or images. It performs no inference, network calls or operational writes. The prepared directory is self-contained; the hosted static Space needs no Python process, dependencies, API keys or compute subscription.

For local inspection, serve this directory with `python -m http.server 8792 --bind 127.0.0.1` and open the printed local URL. The viewer fetches only its own bundled JSON and media. Selection, filtering and trace navigation do not launch a new evaluation.

Static Space metadata follows the [official Hugging Face static Space documentation](https://huggingface.co/docs/hub/spaces-sdks-static). Publication is performed separately by the release owner; source preparation does not prove a public deployment.


## Published application candidate

[Version 0.2.0-rc.1](https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.2.0-rc.1) is published as an engineering candidate, with 9 independently retrieved assets. The 10,122,929-byte application ZIP has SHA-256 `a66a23080654a34133b377c47d549fd83a02907ea6b04805ce272f5619c7273f`; its exact bytes were independently installed and tested (266 passed, 17 skipped). This does not change the recorded model trials, dataset labels or operational-acceptance boundary. The preserved data index/provenance describe their earlier assembly step; their Prepared/publication-performed fields are historical, not a live release-status feed.
