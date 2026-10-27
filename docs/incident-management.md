# Incident management guide

Record actual reported events, verified facts, affected missions, configuration and uncertainty. Assign an accountable commander and responders. Preserve original event timestamps, receipt times, attachments and contact-source references. The software can support lost communications, navigation degradation, unexpected restrictions, severe weather, aircraft faults, battery events, cyber reports, injury/damage, provider outages and fleet suspension as record types; it does not invent aircraft-specific emergency actions.

Use the incident workspace endpoint to retrieve current matching approved procedures and a deterministic escalation assessment. Procedure applicability includes incident type, aircraft configuration, revision, approving actor and validity. Escalation timing comes from the approved procedure. If either is missing, the interface must show the gap and escalate to the accountable person. No arbitrary universal emergency checklist or occurrence-reporting deadline is supplied.

A notification record distinguishes Not Sent, Sent, Delivered, Acknowledged and Action Completed. There is no external emergency-service or authority messaging integration in the candidate. Record authorised manual correspondence and receipts. Reportability, recipients and deadlines require jurisdiction-specific source-backed assessment. Do not assume acknowledgement proves that an action has occurred.

Download the incident workspace JSON and approved procedures for a lawful degraded-mode snapshot. Its generation timestamp makes cache age inspectable. It cannot acquire newer events while disconnected and must never be shown as current live state. Interactive offline reconciliation remains an unverified capability. Recovery after data loss must never create improvised aircraft commands.

After containment and recovery, record findings, corrective actions, owners, due dates, controlled procedure changes and recurrence monitoring. Preserve access restrictions and retention/legal holds. Investigation exports are private operational records and excluded from public software/model releases.
