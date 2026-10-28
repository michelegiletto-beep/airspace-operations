# System Lab programme integration and implementation boundary

The published Multiagentic Systems, Architecture and SPINS dossier was inspected alongside six schema files in the locally installed Multiagentic Platform build. Inspection was read-only: no runtime was launched, no broker interface was invoked and no person was contacted. The public dossier expressly reserves rights to proprietary runtime assets and model material. No such source, schema body, feature recipe, training dataset or weight was copied into this Apache-licensed product.

The installed contracts are specialised for the trading application. For example, the command schema requires stop/target-price and account-related fields. Those fields do not translate into a UAS operating permission or an aircraft command. The installed application was identified by the parent implementation audit as package 1.1.25-rc.50 under its historical installation directory. Its documented native-only mode does not establish active language-model supervision in Airspace.

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
