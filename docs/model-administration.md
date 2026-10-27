# Local model administration

The application remains usable without model services. BM25 retrieval and deterministic operational rules do not require a hosted API. Hosted models are not configured, and no private data is sent to an inference provider by this release.

Download the optional reviewed local retrieval models explicitly:

```powershell
python scripts/prepare_neural.py --component encoder --component reranker
$env:AIRSPACE_NEURAL_RETRIEVAL="local"
$env:AIRSPACE_MODEL_DIR="C:\absolute\product\models\pretrained"
$env:AIRSPACE_INFERENCE_DEVICE="cpu"
```

`prepare_neural.py` checks Apache-2.0 Hub licence metadata at the reviewed commit pinned in `MODEL_REGISTER` and downloads only configuration, tokenizer, safetensors weights, model cards and available licence files. It saves file SHA-256 values and revision provenance. Normal installation does not silently resolve the latest branch. `--refresh` explicitly requests a new upstream revision and records that choice; changed weights require a new evaluation and promotion review. The downloader never enables remote model code or pickle weights. Its default also downloads the small teacher; the successful experiment used the explicitly selected `teacher-base` component. Pretrained files require approximately 92 MB each for the encoder and reranker, 311 MB for the small teacher and 994 MB for the base teacher.

`configure_local_retrieval(organisation_id)` returns scoped model adapters when the environment explicitly selects local inference. The model cache is bounded. Embeddings are cached by organisation scope and text checksum, with no raw source text retained in that cache. Retrieval must apply tenant, jurisdiction, legal-status and date filters before passing any text to the encoder or reranker. An identical private passage in another organisation has a separate cache entry. Missing local files fail visibly; the API records the failure and may continue through its lexical degraded path. No implicit online download occurs during inference.

First use loads local models and encodes eligible source passages, so its latency differs from warm requests. `evaluate_retrieval.py` reports actual cold/warm measurements for its machine and corpus. Its eight queries are exact titles from real official sections, with known structural targets. They are an engineering retrieval proxy, not a qualified legal question-answer benchmark. On the measured GPU run, lexical, hybrid and reranked modes each retrieved all eight expected sections within five results. This tiny title-matching result does not establish broad retrieval quality or legal-answer correctness.

Load the experimental student through `airspace.neural.ExperimentalStudent` with the pinned local encoder. The student safetensors and run manifest are checked separately with `scripts/verify_neural.py`. It is deliberately not automatically promoted into consequential decisions. A review must specify the intended task, dataset rights, accepted baselines, held-out evaluation, known failures and rollback target. The candidate cannot approve its own promotion, amend operational thresholds or modify approval policy.

Keep production, training and replay stores separate. Training accepts only public, rights-cleared legal source passages in this pipeline. Do not copy customer evidence, authority correspondence, personal details or service credentials into the model package or public dataset. Source changes create impact-review tasks; they do not retrain or update weights automatically. Legal source truth remains in the versioned library.

The optional runtime pins are in `requirements-neural.txt`. The original training used older local packages, as its manifest honestly records. The updated release inference environment is tested separately in `release-evidence/neural-current-environment-verification.json`; historical metrics are not rewritten as if training ran with upgraded packages.
