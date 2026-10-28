# System Lab programme integration and implementation boundary

The published Multiagentic Systems, Architecture and SPINS dossier was inspected alongside six schema files in the locally installed Multiagentic Platform build. That contract inspection was read-only: no trading runtime was launched, no broker interface was invoked and no person was contacted. No proprietary trading source, schema body, feature recipe, training dataset or weight was copied into the new coordination core. The public dossier's reserved rights remain intact.

The installed contracts are specialised for the trading application. For example, the command schema requires stop/target-price and account-related fields. Those fields do not translate into a UAS permission or aircraft command. The earlier parent audit observed package 1.1.25-rc.50; later presentation review observed 1.1.25-rc.51 in the same installation directory, whose historical identifier is 1.1.25-rc.31-91768008c6. The installation was updating in place, so the directory name is not a package version and no single version is asserted synchronously at the later copy event. Its native-only trading mode does not establish language-model supervision in Airspace.

## Explicit owned presentation reuse

After the contract inspection, the owner expressly authorised actual reuse of the existing animation technology. The frontend includes a narrowly bounded five-file subset under `frontend/public/vendor/systemlab-companion/`: `mascot-renderer.mjs`, `motion-core.mjs`, `catalog.mjs` and the original Indigo/Coral PNGs. They were copied byte-for-byte and retain reserved proprietary rights, rather than being relicensed under Apache-2.0. The exact hashes, both observed package versions and installation-directory identifier are recorded in [provenance](../frontend/public/vendor/systemlab-companion/provenance.json), with a separate [notice](../frontend/public/vendor/systemlab-companion/NOTICE.md).

The new Apache-2.0 React adapter mounts this presentation-only WebGL/canvas renderer, selects only the two authorised appearances and passes workflow presentation state. Global pause and system reduced-motion preferences force motion off; optimised image/CSS fallback remains usable. Unused original catalogue presentation copy is not shown in the English interface. The module imports no broker/trading engine, model or account integration. This actual runtime-asset reuse is distinct from copying proprietary strategy or training implementation, which did not occur.

Airspace now consumes a new reusable implementation, `backend/systemlab_agentic`, with domain-neutral contracts. Its correspondence with existing programme responsibilities is:

| Inspected contract | New shared implementation and Airspace use |
| --- | --- |
| `SA_ENVELOPE` | `AgentScope` and `TaskContract` bind accountable actor, organisation, domain, causal input snapshot, record revisions and deadline. Airspace adds jurisdiction and operation-date context. |
| `LUNA_COMMAND` | A generated `ToolProposal` is checked against `Capability` and `admit`. No trading parameters or external command semantics are imported. |
| `EXECUTION_RECEIPT` | `ActionReceipt` distinguishes intended work from a recorded completed artifact; external-request acknowledgement is not a confirmed external outcome. |
| `TOOL_READ` | Scoped read adapters use exact version bindings and reject changed or cross-tenant records before consuming results. |
| `WAIT_POLICY` | `WaitPolicy`, bounded leases and explicit pause/cancel handling separate a control request from actual compute release. |
| `CONDITIONAL_PLAN` | Task-specific capability dependencies and persisted step receipts support bounded next-step selection and deterministic post-model state reconciliation. |

These mappings describe a fresh cross-domain implementation aligned with the in-house architectural programme. They do not claim wire compatibility with the installed proprietary contracts, a public legacy SDK, or qualification transferred from trading. The separate `DocumentResearchAdapter` and UAS adapter demonstrate the same new core contract/admission/receipt code operating in two domains through isolated software tests.

Read-only inspection fingerprints identify the exact schema versions examined without redistributing their bodies:

| Schema | SHA-256 |
| --- | --- |
| `SA_ENVELOPE` | `b42781db7b773828250e23960e958454f012e31108ee6d4ac7273b65dd09cb59` |
| `LUNA_COMMAND` | `30357449e9a709bb9b51e4f4f5be3d3c896b1f15af431d83b472c4d27fef454b` |
| `EXECUTION_RECEIPT` | `7c3770a34c62766cfe9c6d3e86db86bbaf528f89e6c5086d52159aa1b71d5fb9` |
| `TOOL_READ` | `44b80e6bf38e242ecd57aff27035a898dd0f0594cde86d74631b968e262f6df2` |
| `WAIT_POLICY` | `374d2955e7096e55b54e91b1528c5e27d3e879246de77c32ab8a1338fc481579` |
| `CONDITIONAL_PLAN` | `3bb1387c9eab49a0335d4704faa91b0536bdbacf80c7f26e177083d0fb8b42d3` |

Executed causal-model orchestration evidence must be reported separately from these source-inspection findings and from synthetic fault-injection tests. Neither multiple model processes nor compatibility of software contracts constitutes independent professional aviation certification.
