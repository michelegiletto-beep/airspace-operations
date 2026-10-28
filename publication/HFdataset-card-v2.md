---
language: en
license: other
license_name: acknowledged-easa-and-eu-legal-text-reuse
license_link: https://www.easa.europa.eu/en/copyright-disclaimer
task_categories:
  - text-classification
pretty_name: System Lab source-linked explicit-language annotations
---

# Source-linked machine annotations

**The 288-row dataset is unchanged.** This documentation update explains its limited role in the 0.2 application architecture. It does not claim new operational data, additional annotation, new expert review or another training run.

![Application context and evidence workflow](media/agent-orchestration.jpg)

*The application screenshot shows workflow context. It is not an observation of a flight or a new dataset example.*

## Contents and provenance

The dataset contains **288 actual English EU legal passages** from EASA reference consolidations, with machine-generated labels and validation records. Forty-two annotations are quarantined; 246 accepted annotations remain unreviewed. It contains no fabricated aircraft operation, customer, flight, authorisation, telemetry, incident, commercial result or human review.

Source families are Regulations 2019/947, 2019/945 and 2021/664. The material was extracted from the actual EASA June 2026 UAS XML and May 2024 U-space XML. Rows preserve source family, archive/XML checksums, edition, eRules section, local block identifier, source URL, upstream metadata and exact source text. Reference consolidations are not asserted to be authentic OJ editions or complete current legal coverage.

Source attribution: European Union Aviation Safety Agency, Easy Access Rules; copyright EASA 2003–2026. EU legal documents: copyright European Union 1998–2026. EASA's copyright notice permits acknowledged reproduction except where otherwise stated. Document-specific restrictions prevail. National research sources, private operator material and paid standards were excluded from this training dataset; code/model licences do not relicense them.

## Annotation task and limitations

The local FLAN-T5-base teacher answers whether the passage contains the English word `shall`. `yes` maps to `explicit_shall`; `no` maps to `no_explicit_shall`. Validation checks the schema and exact source-span support. Unsupported or contradictory labels are quarantined. Each record stores raw output, teacher identity, prompt version/checksum, output schema, source spans, findings and review status. All labels have `human_reviewed: false` and `ground_truth: false`.

Sampling used a literal marker to obtain both strata. Accepted labels were then conditioned on exact-word validation, which makes the deterministic literal-word baseline perfect by construction. A negative label does not mean that the passage imposes no legal obligation: duties may appear in lists, conditions or other wording without `shall`.

Splits are by whole source family: 2019/947 training, 2019/945 validation and 2021/664 testing. Exact case-normalised text duplicates were excluded across splits. Accepted counts are 82, 87 and 77. Only one retrieved edition per family was available, so independent temporal and edition-transition generalisation remain untested. There are no consented operational queries or qualified human-labelled evaluation examples.

## Relationship to the agent platform

![Agent architecture](media/orchestration-pipeline.svg)

The broader application now has actual local causal-LLM orchestration, pretrained retrieval/reranking and deterministic operational specialists. Its new shared `systemlab_agentic` core connects scoped tasks, admitted capabilities, artifacts, receipts and independent review. This small historical annotation dataset trains only an optional experimental routing signal. It does not train the Qwen controller or qualify maintenance, scheduling, country-readiness or permission decisions.

The application also integrates five byte-identical owner-authorised presentation resources for its 2.5D WebGL companions, with reduced-motion, pause and fallback handling in the adapter. The renderer is UI technology, not a neural prediction component. Its reserved assets are not part of this annotation dataset and are not relicensed by this card.

Actual orchestration evidence, the [UI-and-worker workflow](https://github.com/michelegiletto-beep/airspace-operations/blob/main/release-evidence/v0.2.0-rc.1/actual-ui-workflow.json), and the [small source-research comparison](https://github.com/michelegiletto-beep/airspace-operations/blob/main/release-evidence/v0.2.0-rc.1/causal-comparison.json) are separate software-verification records. Four completed native/causal runs over two developer-authored queries do not establish legal-answer reliability, model superiority or expert validation of these annotations. Their elapsed times are affected by run order and cache reuse and do not establish a speed benefit.

The published static evaluation Space makes those recorded runs and this unchanged dataset's source-linked failure cases inspectable. It contains no live inference, operational connection or new training data; its verified link is below.

See the [dataset documentation](https://github.com/michelegiletto-beep/airspace-operations/blob/main/docs/dataset-card.md), [source register](https://github.com/michelegiletto-beep/airspace-operations/blob/main/SOURCE_REGISTER.md), [model card](https://huggingface.co/Magic51/system-lab-airspace-shall-router) and [application repository](https://github.com/michelegiletto-beep/airspace-operations). Do not use this dataset as evidence for flight prediction, approval, dispatch, separation or emergency-instruction systems.


## Inspect the recorded application evidence

The public [System Lab Airspace Evaluation Space](https://huggingface.co/spaces/Magic51/system-lab-airspace-evaluation) contains the actual controller comparison, persisted UI workflow, source citations, unchanged student evaluation and observed failure cases. It is a static recorded-evidence viewer with no model inference or flight-management service. The repository files were independently retrieved at revision `2e7c96760d968f304d9b157f9b63f7b34accf982`; this presentation does not announce new weights or expert ground truth.
