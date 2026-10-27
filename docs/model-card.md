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

# System Lab explicit-language routing student

Run `explicit-shall-20261027-4` is a real, trained experimental neural classifier. It classifies the literal presence of the English word `shall` in a source passage for reviewer routing. Its labels do not assert that a legal obligation exists, applies to an operation, or has been met. It has no dispatch, approval, risk-scoring, air-traffic or aircraft-command authority.

The trained model uses a frozen pretrained `sentence-transformers/all-MiniLM-L6-v2` encoder and a trained 384 → 32 → 2 ReLU MLP with 12,386 trainable parameters. Weights are saved as `student.safetensors`; the complete architecture, SHA-256, training seed, optimisation settings, experiment histories and upstream model revisions are recorded in the run manifest. Upstream encoder and local teacher weights were downloaded under their Apache-2.0 model metadata with remote code disabled. Core release downloads exclude the pretrained weights; the explicit installer retrieves pinned models separately.

The local teacher was `google/flan-t5-base` at revision `7bcac572ce56db69c1ea7c8af255c5d7c9672fc2`. The encoder revision was `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. The teacher annotated 288 real EU legal passages extracted from actual EASA reference consolidations. Exact source-span and schema validation quarantined 42 annotations; 246 remained machine-generated and unreviewed. No record is described as expert ground truth. No operational records were used.

The source-family split used Regulation 2019/947 passages for training (82 accepted), 2019/945 for validation (87), and 2021/664 for testing (77). Exact text duplicates were removed across all splits. Only one retrieved edition per family was available, so independent time and document-version holdouts were not completed. The dataset has English-only and explicit-marker selection bias; unmarked text may still impose real obligations through lists, definitions, conditions or other wording.

Architecture experiments with hidden widths 16, 32 and 64 ran, with width 32 selected by validation loss. The held-out source-family results against filtered machine labels were:

| Method | Held-out agreement | Samples |
| --- | ---: | ---: |
| Trained neural student | 81.82% | 77 |
| Deterministic literal-word baseline | 100.00% | 77 |
| Trained hashed lexical linear classifier | 63.64% | 77 |
| Frozen pretrained label-prototype classifier | 58.44% | 77 |
| Training-majority baseline | 46.75% | 77 |

The student's Wilson 95% interval for this limited agreement measure is 71.76–88.85%; its binary Brier score is 0.153. These are not legal reliability, citation-support or operational acceptance measures. Validation filters deliberately enforce literal marker support, so the deterministic baseline's perfect result follows from the task and filter design. The neural candidate provides no demonstrated production benefit over that baseline and is **Experimental — Not promoted**. Its probabilities are uncalibrated model outputs, never legal-confidence percentages.

Actual training ran on an NVIDIA GeForce RTX 2080 with 8 GB device memory, Python 3.13.1 and PyTorch 2.6.0+cu126. Teacher execution took 18.58 seconds, accepted-passage encoding 0.62 seconds, candidate training 1.14 seconds and the complete successful experiment 21.14 seconds. These measurements describe this run only. CPU inference is supported and separately measured in `release-evidence/neural-cpu-verification.json`; a GPU is optional. Allow about 2 GB of RAM for encoder/reranker inference and at least 4 GB for local teacher work, plus application/database resources. These are conservative installation allowances, not certified minimums.

Three earlier semantic-obligation annotation attempts failed the source/schema/diversity gates and produced no trained model. Their selected passages, teacher raw outputs, quarantines and blocked manifests are preserved in runs 1–3. Small and base FLAN teachers did not produce adequate validated semantic labels. This measured failure drove the narrower explicit-language task. No blocked run is described as successful training.

Required promotion work includes qualified human-reviewed task labels, representative temporal/version/jurisdiction holdouts, unsupported and conflicting provisions, tables and adversarial inputs, calibration where meaningful, and demonstrated benefit over deterministic routing. Production legal reasoning and operational prediction models remain disabled. Model promotion requires an accountable reviewer, documented gates and a rollback decision; the software contains no online self-modification path.

Reproduce from the product directory:

```powershell
python scripts/prepare_neural.py --component encoder --component teacher-base
python scripts/train_neural.py --device cpu --teacher-component teacher-base --per-family 96 --run-id my-reviewed-experiment
python scripts/verify_neural.py --run explicit-shall-20261027-4
```

Run identifiers are append-only. Never overwrite a completed or blocked experiment directory. Dataset/source attribution and upstream model licences remain separate from the newly authored code and student-weight licence.

The student is loaded through the included application code rather than a hosted automatic inference widget:

```python
from airspace.neural import ExperimentalStudent, LocalEncoder

encoder = LocalEncoder("models/pretrained/encoder", device="cpu")
student = ExperimentalStudent("models/runs/explicit-shall-20261027-4", encoder)
results = student.classify([passage["text"]])  # A source-linked library passage.
```
