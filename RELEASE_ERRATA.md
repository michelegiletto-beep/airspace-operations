# Release errata

## 0.1.0-rc.1

The frozen standalone ZIP and tag retain their published identity. The final delivery document check found that the requested `SOURCE_REGISTER.md` human-readable summary was absent. The underlying `sources/catalogue.json`, corpus provenance, source manifests and coverage statement are present. The missing summary is added on `main` as a post-release documentation correction; obtain it from the repository if using the frozen ZIP. This correction does not assert additional source coverage or current legal reconciliation.

The final exact-archive installation report, public retrieval reports, publication status and HANDOVER.md were completed after freezing the ZIP and are published on `main`. They describe the same frozen bytes and do not replace the release assets. `publication/status.json` and `release-evidence/standalone-archive-verification.json` identify the archive by SHA-256.

The frozen capability matrix's ingestion-evidence entry refers to `sources/checks`, which is not a delivered directory. The actual check evidence is `release-evidence/isolated-source-parser.json` and `release-evidence/registered-monitor-real-check.json`. The initial domain-rules note also names OR-Tools 9.14.6206, used during early verification; the frozen dependency lock and clean-install evidence use 9.15.6755. The current domain documentation clarifies this version history. These are documentation corrections and do not change source coverage, tests, code, archive bytes or the tag.

Full acceptance of the original specification, stable release and operational deployment remain blocked as described in HANDOVER.md, capabilities.json and docs/known-limitations.md. This erratum does not waive any gate.
