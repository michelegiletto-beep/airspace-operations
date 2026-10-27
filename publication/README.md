# Publication workflow

Only new project artifacts are published. The existing System Lab portfolio is opened into a separate clean checkout with the official Sites helper, preserving unrelated local changes. Operational instances, databases, object stores and credentials are never copied into public hosting.

1. Run verification and inspect release gates; repair critical security, isolation, approval or core-workflow failures. Stable release remains blocked while original baseline acceptance is incomplete. Engineering candidate assets retain their explicit limitations.
2. Run scripts/package_release.py. Its bounded credential-pattern scan, manifest, SBOM, notices and archive exclude private/runtime/original uncleared materials and unrelated projects. Run scripts/verify_archive.py from a separate directory.
3. Verify the authenticated GitHub namespace and create the new repository, then upload the sanitised source tree, tag the actual source commit and publish the candidate release with ZIP, checksums, SBOM, provenance and release evidence. Never infer publication from a prepared command. Retrieve the public archive and compare its digest.
4. Publish only actual student weights and permitted machine-derived annotations to the verified Hugging Face owner. Preserve cards, source/model licences, lineage, failed experiments and inferior-baseline results. Retrieve the public safetensors/dataset and compare hashes. The Hub is an artifact registry, not the production operations service.
5. Add a sober project page and verified downloadable assets to the existing public System Lab site. Preserve its audience, other pages and identity. The supported Sites source helper owns clean-checkout commit/push/build/package; save/deploy only its exact commit/archive. Retrieve the published download separately.

publication/status.json records Prepared, Uploaded, Published and Independently Retrieved states when each actually happens. Account access, repository creation and uploads use existing accessible accounts. No paid infrastructure, subscription, provider integration or operational customer instance is created.
