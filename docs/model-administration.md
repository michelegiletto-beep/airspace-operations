# Local model administration

The application remains usable without model services. BM25 retrieval and deterministic operational rules do not require a hosted API. Hosted models are not configured, and no private data is sent to an inference provider by this release. Local causal orchestration is an explicitly installed optional path; it is separate from both the narrow trained student and the presentation-only owned mascot renderer.

## Optional local causal controller installation

Start from a core installation using the release's Python 3.13 environment and private database/audit configuration. Install the separate pinned inference requirements, then explicitly download the reviewed retrieval models and controller. These commands download public model files; they do not call a hosted inference API. They are setup instructions, not a claim that a clean deployment has already executed them.

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-neural.txt
.venv/Scripts/python.exe scripts/prepare_neural.py --component encoder --component reranker
.venv/Scripts/python.exe scripts/prepare_controller.py
$env:PYTHONPATH="backend"
$env:AIRSPACE_AGENT_MODEL_DIR=(Resolve-Path "models/pretrained/controller").Path
$env:AIRSPACE_AGENT_DEVICE="cpu"
$env:AIRSPACE_NEURAL_RETRIEVAL="local"
$env:AIRSPACE_MODEL_DIR=(Resolve-Path "models/pretrained").Path
$env:AIRSPACE_INFERENCE_DEVICE="cpu"
```

On Linux use `.venv/bin/python` and equivalent exported environment variables. Python does not automatically load `.env.example`. The API and durable worker need the same tenant database/audit configuration and relevant model-path settings. Start the API as described in README, and run the worker in a separate configured process:

```powershell
.venv/Scripts/python.exe -m airspace.cli worker
```

`prepare_controller.py` takes no model/revision command-line arguments. It explicitly retrieves `Qwen/Qwen3-1.7B` at revision **`70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`** into `models/pretrained/controller`, with anonymous public download, bounded downloader workers and an allowlist of configuration/tokenizer files, safetensors, model card and licence. It records each local file's byte count/SHA-256 and the pinned repository/revision in `provenance.json`. It does not train a System Lab foundation model. The upstream model retains its own licence.

Verify the installed controller identities before enabling it:

```powershell
.venv/Scripts/python.exe -c "from airspace.orchestration import validate_local_model_artifact; print(validate_local_model_artifact('models/pretrained/controller'))"
```

The validator streams every declared file hash, rejects escaped/missing paths and missing safetensor shards, and applies bounded file/weight admission. Loading uses `local_files_only=True`, `trust_remote_code=False` and safetensors. Changed model identity requires reviewed reconciliation; it does not silently replace a controller during a workflow.

The recorded [controller integrity check](../release-evidence/v0.2.0-rc.1/controller-integrity-verification.json) verified **11 files totalling 4,079,448,540 bytes** (about 4.079 GB decimal). That is the downloaded file set, not a RAM requirement or a model-quality result.

| Resource/configuration | Actual behaviour and limit |
| --- | --- |
| CPU controller | Supported by the recorded local runs; float32 weights in memory, with Torch CPU threads capped at four. A GPU is not required for this path. |
| Memory | Must accommodate the loaded controller, encoder/reranker, tokenizers, source index and process overhead. This release has not established a validated minimum RAM/peak-RSS bound; the 4.079 GB disk set is not a claim that 4 GB RAM is sufficient. Measure representative workloads and set deployment resource limits. |
| Disk | Allow the controller file set plus retrieval models, Python dependencies, download caches and private operational/source storage. The release archive excludes the large pretrained model cache. |
| Explicit CUDA path | `AIRSPACE_AGENT_DEVICE=cuda` selects float16 controller loading and requires an appropriate Torch build, device and capacity. The cited causal runs do not establish a CUDA performance or minimum-VRAM result. |
| Retrieval device | `AIRSPACE_INFERENCE_DEVICE` separately controls encoder/reranker loading; `AIRSPACE_MODEL_DIR` locates those downloaded components. |
| Missing model/capacity | Requested model execution blocks, defers or fails with recorded evidence. It does not quietly switch to native work or a hosted provider. |

## Other local modes and retrieval

To select the explicitly labelled FLAN constrained-candidate mode, separately run `.venv/Scripts/python.exe scripts/prepare_neural.py --component teacher-base`. The current adapter uses the project's `models/pretrained/teacher-base` path for this mode; `AIRSPACE_AGENT_MODEL_DIR` applies to the causal controller. FLAN candidate likelihood selection is not presented as free-form generative planning. `native` is an explicitly chosen deterministic reference controller; its specialist retrieval steps can still require the downloaded encoder/reranker.

`prepare_neural.py` checks Apache-2.0 Hub licence metadata at the reviewed commit pinned in `MODEL_REGISTER` and downloads only configuration, tokenizer, safetensors weights, model cards and available licence files. It saves file SHA-256 values and revision provenance. Normal installation does not silently resolve the latest branch. `--refresh` explicitly requests a new upstream revision and records that choice; changed weights require a new evaluation and promotion review. The downloader never enables remote model code or pickle weights. Its default also downloads the small teacher; the successful experiment used the explicitly selected `teacher-base` component. Pretrained files require approximately 92 MB each for the encoder and reranker, 311 MB for the small teacher and 994 MB for the base teacher.

`configure_local_retrieval(organisation_id)` returns scoped model adapters when the environment explicitly selects local inference. The model cache is bounded. Embeddings are cached by organisation scope and text checksum, with no raw source text retained in that cache. Retrieval must apply tenant, jurisdiction, legal-status and date filters before passing any text to the encoder or reranker. An identical private passage in another organisation has a separate cache entry. Missing local files fail visibly; the API records the failure and may continue through its lexical degraded path. No implicit online download occurs during inference.

First use loads local models and encodes eligible source passages, so its latency differs from warm requests. `evaluate_retrieval.py` reports actual cold/warm measurements for its machine and corpus. Its eight queries are exact titles from real official sections, with known structural targets. They are an engineering retrieval proxy, not a qualified legal question-answer benchmark. On the measured GPU run, lexical, hybrid and reranked modes each retrieved all eight expected sections within five results. This tiny title-matching result does not establish broad retrieval quality or legal-answer correctness.

## Distinct recorded causal runs

| Evidence | Observed execution | Interpretation |
| --- | --- | --- |
| [Earlier direct harness](../release-evidence/v0.2.0-rc.1/orchestration-local-20261028T092208Z.json) | Five steps, 204.91 seconds total; first step 169.724 seconds. | Direct `advance_workflow` verification on real public sources in an isolated identity. |
| [Later first UI/durable-worker run](../release-evidence/v0.2.0-rc.1/actual-ui-workflow.json) | Five completed jobs/model calls/tool calls; approximately 305.794 seconds from the first trace start at 10:01:24.400858Z to the final trace finish at 10:06:30.194794Z, rounded to 306 seconds. | Actual application/worker flow and valid audit chain. The timing excludes earlier record preparation/queue time; it is not the earlier 204.91-second run. |

Both used the pinned causal controller and ended at `Needs Review`. The UI run's first complete step spans approximately 252.678 seconds; that does not isolate model setup from source-tool work. Cold/warm caches, requests and execution paths differ, so these observations are not a comparative speed claim or a service-level guarantee. No operational aircraft, flights, customers, telemetry or approvals were created. Broader model reliability, legal quality and operational acceptance remain unestablished by these source-research runs.

`scripts/evaluate_orchestration.py` runs the direct public-source verification into a new isolated runtime. `scripts/evaluate_agent_orchestration.py --mode both --query-count 2 --output <fresh-evidence-path>` compares explicit native/causal paths on developer-authored source-section questions. Choose a new output path; existing evidence is refused rather than overwritten. Neither harness creates flown-flight records or expert ground truth.

## Experimental student and inference service

Load the experimental student through `airspace.neural.ExperimentalStudent` with the pinned local encoder. The student safetensors and run manifest are checked separately with `scripts/verify_neural.py`. It is deliberately not automatically promoted into consequential decisions. A review must specify the intended task, dataset rights, accepted baselines, held-out evaluation, known failures and rollback target. The candidate cannot approve its own promotion, amend operational thresholds or modify approval policy.

The optional standalone authenticated classification service is separate from the durable controller worker. It requires explicit `AIRSPACE_STUDENT_PATH` and `AIRSPACE_ENCODER_PATH` and can run with `python -m airspace.cli inference-serve --host 127.0.0.1 --port 8789` in the configured environment. Its classification output is experimental literal-language routing, not legal confidence or operational permission. The orchestration adapter currently loads its optional historical student from `models/runs/explicit-shall-20261027-4` in process; starting the standalone service does not automatically wire it into another deployment.

Keep production, training and replay stores separate. Training accepts only public, rights-cleared legal source passages in this pipeline. Do not copy customer evidence, authority correspondence, personal details or service credentials into the model package or public dataset. Source changes create impact-review tasks; they do not retrain or update weights automatically. Legal source truth remains in the versioned library.

The optional runtime pins are in `requirements-neural.txt`. The original training used older local packages, as its manifest honestly records. The updated release inference environment is tested separately in `release-evidence/neural-current-environment-verification.json`; historical metrics are not rewritten as if training ran with upgraded packages.
