# Agent contracts and integration

`backend/systemlab_agentic` is a newly authored domain-neutral coordination core. The Airspace adapter in `airspace.orchestration` imports its task, scope, budget, capability, artifact, receipt, wait, admission and reconciliation contracts. A separate read-only `DocumentResearchAdapter` uses the same core without aviation or trading entities. Contract tests exercise both adapters. This is an actual shared module, not an assertion that an existing proprietary trading runtime supports UAS operations.

The new backend core contains no proprietary trading source/parameters, SPINS recipes, model weights or copied schema bodies. Public architectural responsibilities informed a fresh implementation. Its code licence does not change the installed Multiagentic Platform's rights. Separately, the frontend now reuses five already distributed owned presentation resources byte-for-byte under reserved rights: three browser renderer/motion/catalogue modules and two mascot PNGs. A fresh Apache-2.0 React adapter passes only presentation state and preserves pause/reduced-motion/image fallback. See [implementation mapping](multiagentic-contract-mapping.md) and the [vendor notice](../frontend/public/vendor/systemlab-companion/NOTICE.md). Presentation reuse imports no trading execution or private training implementation.

## API and worker integration

The module exports:

```python
repository = WorkflowRepository(store)
workflow = repository.create(validated_request, authenticated_actor)
workflow = repository.get(workflow_id, organisation_id)
items = repository.list(organisation_id)
workflow = repository.control(workflow_id, authenticated_actor, action, expected_version)
workflow = advance_workflow(store, workflow_id, authenticated_actor,
                            expected_version=expected_version, services=services)
catalogue = capability_catalog()
```

`advance_workflow` performs one bounded, persisted step. Reuse `default_services()` within a worker process to retain loaded neural models. API handlers authenticate the user and map `OrchestrationError` to a scoped validation/version response. Dedicated routes should expose create/list/get, control with `{action, expected_version}`, and advance with `{expected_version}`. The worker invokes the same function under the original accountable actor. `agent_workflow` records must remain protected from generic record editing or approval endpoints.

Requests declare `task_kind`, `objective`, `jurisdiction`, `operation_date`, optional `context_record_ids`, optional SORA `methodology`, `include_experimental_student`, `controller_mode` and a bounded `budget`. Organisation, actor, role and exact record-version bindings are constructed on the server. Requests cannot set tool permissions, issuer decisions, organisation identity or independent approvals. `capability_catalog()` returns the actual Pydantic schemas rather than an independently maintained approximate contract.

Supported task kinds are regulatory research, authorisation preparation, site assessment and scheduling proposals. The server derives the allowed specialist graph for each task. The language model chooses its next admitted tool using completed receipts; the server separately revalidates scope, permissions, budget and dependencies before execution. Outputs record the real selected proposal, controller revision, prompt/response checksums, source/model versions, exact input/output snapshots, accountable actor and timestamps.

Operational task kinds also include maintenance planning, cross-border readiness and fleet-sharing review. Their tools call the actual maintenance assessment/planning/verifier, country-segment readiness and sharing-consent modules. They consume `data.maintenance_assessment`, `data.maintenance_plan_input`, mission `data.coordination`, or persisted schedule assignments. They cannot create a maintenance release, country instrument, sharing consent or reservation. Missing records or typed contracts remain visibly missing. Resource and issuer bindings in a scoped schedule are included in its causal snapshot and independently checked before the scheduling tool runs.

Actual capabilities include pretrained neural source retrieval, neural cross-encoder reranking, an explicitly optional experimental student signal, deterministic case evidence gaps, SORA evidence checks, spatial screening, CP-SAT scheduling and an independent schedule verifier. Missing typed inputs produce explicit missing-input artifacts. SORA records supply `data.assessment_input` conforming to `RiskRequest`; sites supply `data.screening_input` conforming to `SiteScreenRequest`; existing schedule records supply `data.input` conforming to `ScheduleRequest`. The tools never invent values to complete these contracts.

The controlled draft is assembled from exact source quotations and specialist artifacts. It deliberately makes no machine legal conclusion. Its review gate requires an independent accountable reviewer. No controller capability grants an operating permission, submits an application, sends correspondence, reserves resources, releases dispatch or commands an aircraft.

## Local language-model controller

`LocalCausalController` uses an explicitly installed local causal model through `AutoModelForCausalLM`, safetensors and `trust_remote_code=False`. It reads a local provenance manifest, uses the model's chat template with thinking output disabled, and actually generates a JSON next-tool proposal. Whole-output JSON parsing, a strict Pydantic schema and deterministic capability admission reject prose, extra fields, invented tools and dependency bypasses. The model does not merely decorate an already executed schedule or return a fixed canned dashboard result.

Before loading a causal controller, the module streams and verifies every declared local file against its SHA-256 manifest, rejects missing tensor shards and paths outside the configured model directory, and applies an explicit file/weight-size admission bound. [Actual integrity verification](../release-evidence/v0.2.0-rc.1/controller-integrity-verification.json) checked all 11 pinned controller files (4,079,448,540 bytes). That is an identity check, not proof of model quality or safe legal judgement.

Configure the controller with `AIRSPACE_AGENT_MODEL_DIR` and `AIRSPACE_AGENT_DEVICE=cpu` or `cuda`. The model directory must contain a provenance record with `repository` and pinned `revision`. The new controller uses no hosted provider, credentials or external inference API. External-provider support is not enabled by an API switch.

`local_flan` is separately labelled constrained-candidate likelihood selection through the cached FLAN-T5 model; it is not described as generative planning. `native` is an explicitly selected deterministic reference controller. An unavailable causal model blocks or retries the requested causal workflow; the product does not silently call native work an LLM run.

The historical literal-`shall` student remains a narrow, unpromoted experimental artifact. It does not supply the supervisory intelligence, interpret obligations or replace the pretrained neural retrieval and causal controller. Its task limitations and measured failure to beat the deterministic baseline remain in its model card. This integration does not manufacture additional training or new benchmark results for that student.

## Durability and operational boundaries

Workflow state uses the existing transactional records, version snapshots and tamper-evident audit chain. Each claim stores an inference/tool lease before computation. Compare-and-swap updates reject concurrent edits. Pause and cancellation retain the active compute identity until the model call returns; a late result is discarded and physical return is recorded. Expired read-only claims may recover with an explicit reconciliation receipt. Uncertain external actions cannot be retried by this controller because no external action tool is exposed.

Changes to bound records, actor permissions or artifact checksums require reconciliation. The supervisory prompt receives only task text, scoped record kinds and structured receipt summaries; raw uploaded/source bodies do not become supervisory instructions. Tenant and date filters precede neural retrieval. A single local causal inference slot and bounded model cache prevent concurrent controller admission from silently oversubscribing the same model.

Source admission is bounded to 128 files, 256 MiB total serialized source input, 25,000 distinct passages and 50,000 characters per passage in this adapter. Exceeding a limit rejects the request and requires a narrower reviewed index; it does not silently search a subset. The first accepted controller revision is fixed for the workflow. A model change requires reconciliation rather than silently changing the policy halfway through a task.

Inference cancellation and time limits are checked at token boundaries. A currently executing tensor operation may finish after the requested deadline; output exceeding the declared budget is withheld. Tool deadlines are also checked before consuming returned results. These mechanisms are not hard real-time aviation guarantees. Managed deployments still require process/container resource limits and measured workload-specific acceptance.

The final state is `Needs Review`, not `Approved`. Model outages, capacity deferral, source gaps and changed inputs remain visible. The software is a decision-support workflow and does not provide certified separation, Detect and Avoid, ATC, autopilot or authority-issued permissions.

## Executed evidence and comparison limits

Two separate executed records must not be conflated. [The earlier direct local harness run](../release-evidence/v0.2.0-rc.1/orchestration-local-20261028T092208Z.json) executed Qwen3-1.7B at pinned revision `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` and completed five proposals/tools in 204.91 seconds, ending at `Needs Review`. Its first cold step took 169.724 seconds, including setup/source encoding; subsequent steps were approximately 8.5–9.5 seconds.

[The later actual UI/durable-worker run](../release-evidence/v0.2.0-rc.1/actual-ui-workflow.json) asked about the U-space UAS flight-authorisation service and recorded five completed jobs, five model/tool calls and a valid audit chain. Its five trace steps span approximately **305.794 seconds** (10:01:24.400858Z to 10:06:30.194794Z), conventionally rounded to 306 seconds. This excludes earlier record preparation/queue time. It also ended at `Needs Review`, with no operational aircraft, flights, customers, approvals or telemetry created. Both runs used genuine public-source material; neither duration establishes comparative speed, reliability, legal quality or operational acceptance. See [local model administration](model-administration.md) for installation, hardware boundaries and the distinct measurements.

`scripts/evaluate_agent_orchestration.py` provides an append-only evidence harness for 1–3 developer-authored source-grounded queries and a native-controller reference. It records actual inference, target-section retrieval proxies, failures, latency, review gates and full receipts. No comparative advantage is assumed merely because a generative controller successfully invokes the same tools. Broader representative operator tasks, independent domain review and deployment-specific performance remain required.
