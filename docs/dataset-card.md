---
language: en
license: other
license_name: easa-eu-legal-text-reuse-with-attribution
license_link: https://www.easa.europa.eu/en/copyright-disclaimer
task_categories:
  - text-classification
pretty_name: System Lab source-linked explicit-language annotations
---

# Source-linked machine annotations

The successful experimental dataset contains 288 actual English EU legal passages with machine-generated annotations, of which 42 are quarantined. It contains no fabricated operation, flight, customer, incident, authorisation, measurement or human review. The source documents are reference consolidations downloaded from EASA, not asserted authentic OJ editions.

Source families are Regulations 2019/947, 2019/945 and 2021/664. Text is extracted from the EASA June 2026 UAS XML and May 2024 U-space XML. Dataset rows preserve source ID, source family, archive checksum, XML checksum, edition, original eRules section, local block, source URL, upstream regulatory metadata and exact text. Table rows in the complete library preserve cell boundaries; this small classification experiment uses eligible legal text between 60 and 700 characters. AMC and guidance, national procedures and private operator records were excluded from student training.

Source attribution: European Union Aviation Safety Agency, Easy Access Rules; copyright EASA 2003–2026. EU legal documents: copyright European Union 1998–2026. EASA's copyright notice permits reproduction with source acknowledgement except where otherwise stated. Source-specific restrictions take precedence. Model and code licences do not relicense documents. National source rights are unconfirmed and those materials are not included in the training dataset or public redistribution set.

The local FLAN-T5-base teacher answers whether a passage contains the word `shall`. `yes` maps to `explicit_shall`; `no` maps to `no_explicit_shall`. The validator accepts only schema-conforming outputs whose literal source-span support agrees with the text. Unsupported and contradictory labels are quarantined. Every annotation stores raw output, teacher identity, prompt version and checksum, output schema, exact source spans, validation findings, review status and a text checksum. All annotations have `human_reviewed: false` and `ground_truth: false`.

The examples were stratified by a literal marker to ensure both sampling strata. This is machine-derived sampling, not expert labelling. Validation then conditions the dataset on agreement with an exact-word check. Consequently the deterministic word baseline performs perfectly by construction. The student experiment measures a real neural network's ability to reproduce these filtered annotations; it does not measure interpretation of real legal duties. Negative labels must not be treated as absence of a real obligation.

Splits are by whole source family: 2019/947 training, 2019/945 validation and 2021/664 testing. Exact case-normalised text duplicates are excluded across splits. No random chunk split is used. The accepted split counts are 82, 87 and 77 respectively. Only one snapshot edition per family is present; temporal generalisation and edition-transition reliability remain untested. Earlier failed annotation runs retain their own immutable lineage and are not silently combined with this dataset.

The release files are `models/runs/explicit-shall-20261027-4/dataset.jsonl`, `selected-passages.json`, `annotations.json` and `run.json`. These source-linked derivatives are machine annotation records, not observations of any UAS operation. No consented operational queries or qualified human-labelled examples were available. Do not use the dataset to train flight prediction, approval, dispatch, separation or emergency-instruction systems.
