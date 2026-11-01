# Release 0.3.3-rc.1

Engineering candidate for self-hosted civilian UAS planning and decision support. The original specification remains incomplete. Stable release and operational acceptance remain false.

Saved-task loading distinguishes an unsuccessful request from a successfully retrieved empty list. When the task request fails, the companion offers a direct retry for that request. Loading, failure and confirmed empty states remain separate, so an unavailable service does not imply that the user has no saved work. Retrying the list does not create a task, send a model request or change an operational record.

The shared read-only request hook cancels outdated requests and binds returned data and errors to the current request context. A late response from an earlier path, authentication context or refresh cannot replace the current view. This interface protection supplements the existing server-enforced tenant, actor and permission boundaries; it does not grant access or approval rights. Independent backend and interface checks remain required for this candidate.

Current release notes include the published 0.3.2 candidate in their history. The generated historical 0.3.0, 0.3.1 and 0.3.2 history lines remain unchanged. Candidate media uses its own namespace and a correctly named JPEG capture; previous tags, archives, source bytes and evidence are preserved. No fictional operational records or placeholder screenshots are included.

The PyPDF 6.21.4 pin introduced in 0.3.2 is retained. No new dependency, model provider, aircraft command, external correspondence tool, authority decision, external submission or self-approval is added. Typed internal draft actions still require explicit confirmation, current actor permissions and input versions. The owned companion and animated fallback continue to honour saved pause and reduced-motion preferences.

No new local-model generation, student training, operational prediction or model-performance improvement is claimed. Existing experimental weights and datasets remain unchanged. A pristine operational workspace remains empty. Schema marker 3 is unchanged; use the existing upgrade, backup and restoration instructions. Qualified national review, lawful operational data, approved procedures and operator acceptance remain required.
