---
language: en
license: other
license_name: acknowledged-easa-and-eu-legal-text-reuse
license_link: https://www.easa.europa.eu/en/copyright-disclaimer
task_categories:
  - text-classification
pretty_name: System Lab source annotations
---

# System Lab source annotations

This dataset contains 288 actual English EU legal passages and their machine annotation records. Forty-two annotations are quarantined. The 246 accepted annotations remain unreviewed machine outputs, not expert ground truth.

This card accompanies the published 0.3.2 application candidate. Dataset rows, checksums, labels, splits and review status are unchanged. No new operational observations, annotations, expert review or training run are claimed.

## Application release context

The published 0.3.2 source is [2ebb8b20e515d9863a69b072bd963890e219e050](https://github.com/michelegiletto-beep/airspace-operations/tree/2ebb8b20e515d9863a69b072bd963890e219e050). It adds Operations role guidance and bounded publication-media checks. It also pins the upstream PDF parser to 6.21.4 for [GHSA-5849-834g-hvw5](https://github.com/py-pdf/pypdf/security/advisories/GHSA-5849-834g-hvw5), [GHSA-mfr5-77xh-9j7h](https://github.com/py-pdf/pypdf/security/advisories/GHSA-mfr5-77xh-9j7h), [GHSA-cggf-277g-3q54](https://github.com/py-pdf/pypdf/security/advisories/GHSA-cggf-277g-3q54); see the [upstream fixed release](https://github.com/py-pdf/pypdf/releases/tag/6.21.4). This dependency change does not relabel, regenerate or validate these historical annotations.

The 0.3.2 application release and all nine public assets are independently retrieved. Its 13,796,258-byte ZIP has SHA-256 `1634b9b7e36bd2b80b179a4e0429da7f0c9165434747fc9a62f03ede78cc772e`. Source and exact-archive software suites each passed 542 tests with 20 skipped; 132 interface tests and 19 PostgreSQL checks are recorded in [CI41275818880](https://github.com/michelegiletto-beep/airspace-operations/actions/runs/41275818880). These application checks do not qualify the historical annotations. No new weights, labels, splits or benchmark results are part of this presentation update.

## Sources

The source families are Regulations 2019/947, 2019/945 and 2021/664, extracted from actual EASA June 2026 UAS XML and May 2024 U-space XML reference consolidations. Rows retain source family, archive/XML checksum, edition, section/block anchors, source URL, upstream metadata and exact text.

These reference consolidations do not establish authentic Official Journal editions or complete current legal coverage. Material is attributed to the European Union Aviation Safety Agency, Easy Access Rules, copyright EASA 2003â€“2026; EU legal documents copyright European Union 1998â€“2026. EASA's acknowledged reproduction terms apply except where otherwise stated. Document-specific restrictions prevail.

The dataset contains no private operator material, paid standards, consented operational queries or fabricated flights, aircraft, authorisations, telemetry, incidents, customers or commercial results. Original source language and legal meaning are not changed to satisfy presentation style.

## Annotation

The local FLAN-T5-base teacher answered whether the passage contains the English word `shall`. `yes` maps to `explicit_shall`; `no` maps to `no_explicit_shall`. Validation checks the schema and exact source spans. Unsupported and contradictory annotations are quarantined.

Each record keeps raw teacher output, teacher identity, prompt version/checksum, output schema, source spans, validation findings and review state. All labels have `human_reviewed: false` and `ground_truth: false`.

Sampling and validation condition the task on literal support. A negative label does not mean that no obligation exists. A duty may be expressed in a list, condition or another wording.

## Splits and evaluation limits

Whole source families form the splits: 2019/947 training, 2019/945 validation and 2021/664 testing. Accepted counts are 82, 87 and 77. Exact case-normalised duplicate text was excluded across splits. Only one retrieved edition per family was available, so temporal and edition-transition generalisation remain untested.

The associated student reached 81.82% agreement on 77 machine labels, while a deterministic literal-word check reached 100%. The filter/task design explains the deterministic result. These are not legal correctness scores. Three failed earlier semantic annotation attempts remain documented.

This historical dataset does not train the application's Qwen controller or qualify maintenance, country permissions, scheduling, dispatch or flight decisions. The application changes through the 0.3.2 release do not add factual training evidence.

Read the [dataset documentation](https://github.com/michelegiletto-beep/airspace-operations/blob/v0.3.1-rc.1/docs/dataset-card.md), [source register](https://github.com/michelegiletto-beep/airspace-operations/blob/v0.3.1-rc.1/SOURCE_REGISTER.md), [student model card](https://huggingface.co/Magic51/system-lab-airspace-shall-router) and [recorded evidence viewer](https://huggingface.co/spaces/Magic51/system-lab-airspace-evaluation). The viewer performs no live inference or operational management.

Source documents retain their own terms. Application-code and model licences do not relicense them. Existing System Lab artwork and presentation files are not part of this dataset.

The 0.3.2 publication changes only the application presentation. No dataset rows, original checksums, annotations, weights or evaluation results are replaced by this card update. Application screenshots are kept outside the dataset records and do not become factual training evidence.
