---
language: en
license: apache-2.0
library_name: pytorch
pipeline_tag: text-classification
base_model: sentence-transformers/all-MiniLM-L6-v2
tags:
  - experimental
  - requires-review
---

# System Lab experimental literal-language routing student

This repository contains a small experimental classifier for the literal presence of the English word `shall`. It does not determine whether a legal obligation exists, applies or has been met.

This card is Prepared for the 0.3 application revision. The student weights, original dataset, training run and measured results are unchanged. No new training or improved performance is claimed. Application interaction and animation changes are separate from this model and require their own verification.

## Model

Run `explicit-shall-20261027-4` uses a frozen MiniLM encoder and a 384 to 32 to 2 ReLU classifier with 12,386 trainable parameters. The student safetensors file is 49,824 bytes, SHA-256 `ff96770308c96b9d96c5f8f6535576e9d791834f76291bf08fce99dcf34d6e6c`.

The separately loaded encoder is `sentence-transformers/all-MiniLM-L6-v2` at revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Encoder weights and the application's optional Qwen controller are not included in this student file. Model identity does not establish legal or operational reliability.

## Data and results

A local FLAN-T5-base teacher annotated 288 actual English EU legal passages. Source and schema checks quarantined 42 annotations. The remaining 246 accepted annotations are machine generated and unreviewed. They are not expert ground truth.

Whole source families define the splits: Regulation 2019/947 for training, 2019/945 for validation and 2021/664 for testing. Accepted counts are 82, 87 and 77. Exact text overlap was excluded. Independent time and edition holdouts were unavailable.

| Method | Agreement with held-out machine labels | Samples |
| --- | ---: | ---: |
| Student | 81.82% | 77 |
| Deterministic literal-word check | 100.00% | 77 |
| Trained hashed lexical baseline | 63.64% | 77 |
| Frozen pretrained prototype | 58.44% | 77 |
| Training-majority baseline | 46.75% | 77 |

The student's Wilson 95% interval is 71.76 to 88.85% for this limited agreement measure. Its Brier score is 0.153. The exact-word validation filter makes the deterministic baseline perfect by design. The student has not demonstrated a benefit over that baseline and remains experimental and unpromoted. Its probabilities are not calibrated legal confidence.

Three earlier semantic annotation attempts failed and remain in the lineage. Historical training used the recorded PyTorch 2.6.0+cu126 environment; later inference dependency updates did not constitute retraining.

## Use and limits

The application can display the result as an optional routing signal for review. It must not approve a case, permission, maintenance release, schedule, dispatch or emergency action. No operational prediction model was trained.

Load through `airspace.neural.ExperimentalStudent` with the pinned encoder. There is no hosted model service configured by this card. The [public evidence Space](https://huggingface.co/spaces/Magic51/system-lab-airspace-evaluation) displays recorded evidence and performs no live inference. The [application repository](https://github.com/michelegiletto-beep/airspace-operations) provides actual installation and release status. The new 0.3 candidate remains Prepared until its own checks and publication receipts exist.

Promotion would require qualified human labels, representative evaluation across dates, versions and jurisdictions, appropriate calibration and a demonstrated practical benefit. Another model's agreement is not expert review.

The student/code licence does not relicense source documents, upstream models or existing System Lab artwork and presentation files. Those retain their own rights. This documentation preparation does not change the previously published weights.
