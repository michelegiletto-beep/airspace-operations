---
language: en
license: apache-2.0
library_name: pytorch
pipeline_tag: text-classification
base_model: sentence-transformers/all-MiniLM-L6-v2
tags:
  - experimental
  - regulatory-document-routing
  - requires-review
---

# System Lab experimental literal-language routing student

**The trained student artifact is unchanged.** This documentation update places it within the 0.2 Airspace agent architecture; it does not announce new student weights, further training or improved performance. This repository contains the small experimental routing student, not the Qwen controller or a production UAS operations service.

![Application workflow context](media/agent-orchestration.jpg)

*Application context: persisted specialist execution and an independent-review gate. The screenshot does not constitute new training data or evidence that this student authorises an operation.*

## Its role in the application

![Agent execution architecture](media/orchestration-pipeline.svg)

System Lab Airspace Operations now uses a local generative controller to propose bounded specialist work. The actual controller is pretrained **Qwen3-1.7B**, pinned at `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`. Pretrained embeddings and a cross-encoder retrieve and rank source evidence. Deterministic rules, optimisation, independent verification and approval gates retain operational authority.

This student supplies an **optional, unpromoted literal-language signal** inside that wider workflow. It is not the supervisory controller, a semantic legal-obligation model or an operational predictor. The new `systemlab_agentic` core is fresh shared coordination code aligned with the [System Labs multiagentic systems programme](https://giletto-systems-lab.michele-giletto.chatgpt.site/projects/multiagentic-systems); proprietary trading/SPINS weights and source were not copied.

The product's companions use an owner-authorised 2.5D WebGL presentation runtime, with five distributed resources preserved byte-for-byte. Reduced-motion, pause and static-image fallback belong to that UI adapter. They do not make this student a rendering model or provide operational authority. The presentation files retain reserved rights, separate from the newly authored shared core and student weights.

The [first actual causal-controller execution](https://github.com/michelegiletto-beep/airspace-operations/blob/main/release-evidence/v0.2.0-rc.1/orchestration-local-20261028T092208Z.json) generated five JSON proposals, invoked actual neural tools and ended at **Needs Review** in 204.91 seconds. A [separate actual UI workflow](https://github.com/michelegiletto-beep/airspace-operations/blob/main/release-evidence/v0.2.0-rc.1/actual-ui-workflow.json) records its own five steps and timestamps. A [four-run, two-query comparison](https://github.com/michelegiletto-beep/airspace-operations/blob/main/release-evidence/v0.2.0-rc.1/causal-comparison.json) is a tiny source-research proxy, not proof of superiority or legal-answer reliability; its timings are confounded by run order and cache reuse. These records do not change this student's training metrics or promotion status.

## Model identity and intended task

Run `explicit-shall-20261027-4` trained a frozen MiniLM encoder plus a 384 → 32 → 2 ReLU MLP with **12,386 trainable parameters**. It classifies the literal presence of the English word `shall` for reviewer routing. The labels do not establish whether a legal obligation exists, applies or has been met.

The student safetensors file is **49,824 bytes**, SHA-256 `ff96770308c96b9d96c5f8f6535576e9d791834f76291bf08fce99dcf34d6e6c`. The local encoder is `sentence-transformers/all-MiniLM-L6-v2` at `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. It is loaded separately; the encoder and Qwen weights are not bundled into this small student artifact. The training manifest records complete architecture, upstream revisions, seed, histories and lineage.

## Dataset and measured evaluation

The local FLAN-T5-base teacher annotated **288 actual EU legal passages**. Schema and exact-source-span checks quarantined 42 annotations; 246 accepted rows remain machine-generated and unreviewed. No example is expert ground truth. Training, validation and test families were 2019/947, 2019/945 and 2021/664, with accepted counts 82, 87 and 77. Exact text overlap was excluded; independent time/version holdouts were unavailable.

| Method | Held-out machine-label agreement | Samples |
| --- | ---: | ---: |
| Trained student | 81.82% | 77 |
| Deterministic literal-word baseline | 100.00% | 77 |
| Trained hashed lexical linear baseline | 63.64% | 77 |
| Frozen pretrained prototype baseline | 58.44% | 77 |
| Training-majority baseline | 46.75% | 77 |

The student's Wilson 95% interval is 71.76–88.85% for this limited agreement measure; its Brier score is 0.153. The source-span filter conditions accepted labels on literal support, so the deterministic baseline's perfect result follows from the task/filter design. **The student has not demonstrated a production benefit over that baseline and remains Experimental — Not promoted.** Probabilities are uncalibrated model outputs, not legal confidence.

Three earlier semantic-obligation annotation attempts failed their gates and remain recorded. The successful narrower task does not conceal those failures or establish semantic extraction quality. Original training used the historical PyTorch 2.6.0+cu126 environment recorded in the manifest. Later CPU inference verification used upgraded dependencies; historical training results were not rewritten as if training had been repeated.

## Use and boundaries

Load the student through `airspace.neural.ExperimentalStudent` with the pinned local encoder. There is no configured hosted inference service. The published static evaluation Space presents the actual recorded comparison, UI workflow, source passages and original model evaluation. It performs no live inference and is not the production operations platform; its verified link is below. The downloadable application, setup, dataset documentation and actual verification are in the [source repository](https://github.com/michelegiletto-beep/airspace-operations).

Promotion requires qualified human-reviewed task labels, representative temporal/version/jurisdiction evaluation, calibration where useful and demonstrated benefit over deterministic routing. The student must not approve permissions, score operational safety, control dispatch, issue emergency instructions or command aircraft. No operational prediction model was trained.

New student weights and code use their stated Apache-2.0 licence. Source passages, upstream models and screenshots/artwork retain separate rights. This documentation update does not relicense source documents or proprietary System Lab artwork.


## Inspect the recorded application evidence

The public [System Lab Airspace Evaluation Space](https://huggingface.co/spaces/Magic51/system-lab-airspace-evaluation) contains the actual controller comparison, persisted UI workflow, source citations, unchanged student evaluation and observed failure cases. It is a static recorded-evidence viewer with no model inference or flight-management service. The repository files were independently retrieved at revision `2e7c96760d968f304d9b157f9b63f7b34accf982`; this presentation does not announce new weights or expert ground truth.
