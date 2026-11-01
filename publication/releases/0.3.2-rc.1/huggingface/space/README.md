---
title: System Lab Airspace Evaluation
sdk: static
app_file: index.html
license: apache-2.0
---

# System Lab Airspace Evaluation

A static viewer of recorded software and model evidence. It is separate from an authenticated operational installation and performs no live inference or external action.

## Current application candidate

Version 0.3.2-rc.1 is a published engineering candidate from source [2ebb8b20e515d9863a69b072bd963890e219e050](https://github.com/michelegiletto-beep/airspace-operations/tree/2ebb8b20e515d9863a69b072bd963890e219e050). Its 13,796,258-byte ZIP has SHA-256 `1634b9b7e36bd2b80b179a4e0429da7f0c9165434747fc9a62f03ede78cc772e`. All nine public release assets were independently retrieved and matched their published digests. [Download the 0.3.2 ZIP](https://github.com/michelegiletto-beep/airspace-operations/releases/download/v0.3.2-rc.1/System-Lab-Airspace-Operations-0.3.2-rc.1.zip) or [inspect its release and verification assets](https://github.com/michelegiletto-beep/airspace-operations/releases/tag/v0.3.2-rc.1).

The Operations workspace now explains that a regulatory user can inspect mission records while the planner or pilot role is required to create a mission proposal. Disabled controls have an accessible explanation and a separate link opens authorisation cases. Server permissions remain authoritative. The candidate also integrates bounded publication-media encoding checks and correct filenames for new JPEG captures.

The candidate pins `pypdf==6.21.4` for the upstream denial-of-service advisories [GHSA-5849-834g-hvw5](https://github.com/py-pdf/pypdf/security/advisories/GHSA-5849-834g-hvw5), [GHSA-mfr5-77xh-9j7h](https://github.com/py-pdf/pypdf/security/advisories/GHSA-mfr5-77xh-9j7h), [GHSA-cggf-277g-3q54](https://github.com/py-pdf/pypdf/security/advisories/GHSA-cggf-277g-3q54). The initial audit found three advisories in the previous 6.21.3 pin; the failed record is preserved. Local corrected core, frontend and optional-neural scans found no known findings in their selected inputs. This is not a claim that the software is vulnerability-free. The fixed upstream release is [PyPDF 6.21.4](https://github.com/py-pdf/pypdf/releases/tag/6.21.4). Frozen 0.3.1 retains its affected 6.21.3 pin; an existing installation is not updated by a new publication.

The actual current source and exact-archive suites each passed 542 tests with 20 skipped. The interface suite passed 132 tests. Nineteen PostgreSQL checks, actual containers, worker/API completion and backup/restoration passed in [CI41275818880](https://github.com/michelegiletto-beep/airspace-operations/actions/runs/41275818880). The exact archive suite completed in 67.80 seconds. These software checks do not establish aviation certification, complete European coverage or operational acceptance. No new model generation, student training, dataset rows or model-performance improvement accompanies this candidate.

![Actual 0.3.2 Operations role guidance](media/operations-permissions-mobile.jpg)

Actual mobile capture from the 0.3.2 software review shows an empty operational workspace and the regulatory-role explanation. It is recorded software evidence, not a flight, customer record, model reply or training example. Existing companion artwork and presentation rights remain reserved as set out in [NOTICE.md](NOTICE.md).


## Historical published software

The 0.3.1-rc.1 release remains available as an unchanged historical candidate. Its 12,504,321-byte ZIP has SHA-256 `0917f468624e35c64829f1591d389fadf51f4528f027d7dc614f1c3fb2b7b750`. Its exact archive passed 479 tests with 20 skipped, with 19 PostgreSQL checks and 123 interface tests recorded separately in [CI41118769822](https://github.com/michelegiletto-beep/airspace-operations/actions/runs/41118769822). These are historical 0.3.1 results, not current 0.3.2 installation evidence.

The historical desktop screenshot is labelled 0.3.1. The new mobile JPEG belongs to the 0.3.2 software review. Old media, original model weights, dataset rows and evidence remain unchanged. The original mobile 0.3.1 capture has JPEG bytes under a `.png` filename in the frozen release; the existing byte-identical `.jpg` presentation copy is preserved.

The experimental student remains unpromoted. No full European coverage, certified service or operational acceptance is claimed. Source documents, upstream models, student files and owned artwork retain their separate rights. The complete historical rights notice is preserved in [NOTICE.md](NOTICE.md).
