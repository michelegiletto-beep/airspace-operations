# Hugging Face presentation update

State on 31 October 2026: **Published and independently retrieved**. The ten reviewed targets were uploaded through the existing authenticated Magic51 browser session. Exact revisions are model `a6a24fc396ce7e86eb9f9c096231f0378e355ef7`, dataset `88c470dd521d63a90a6361e762e73167823317a1` and static Space `7aae1c50c4a7556d3f067bcf8992cf8219fa51cf`. All target bytes and 33 unlisted historical files were independently retrieved and match. Two exact provider-generated LFS path entries are recorded separately. See [the publication record](../../../../docs/huggingface-publication.md). The manifest and preparation receipts retain their dated Prepared state; they are not the current publication-status record. No account, new model artifact, dataset record or live inference service was created.

`manifest.json` lists exactly ten permitted upload targets, their destination repository, repository type, relative target, size and SHA-256. Upload only those files after confirming the existing account and exact write permissions. Preserve every unlisted file, original weight, dataset row and historical evidence artifact. Re-read each destination's current immutable revision before writing, reconcile any newer edits and record the old and resulting commit identifiers for rollback.

The model and dataset cards describe the unchanged experimental student and unreviewed machine annotations. The static Space presents the published 0.3.1 application, correct download digest and actual screenshots. It runs no inference and exposes no operational controls. The copied mobile JPEG uses a `.jpg` filename; its bytes remain identical to the misnamed capture in the frozen release. No published screenshot, source tag or archive is replaced.

Run from the product root:

```text
.venv/Scripts/python.exe -B publication/releases/0.3.1-rc.1/huggingface/prepare.py
.venv/Scripts/python.exe -B publication/releases/0.3.1-rc.1/huggingface/verify_preparation.py
```

Preparation and validation perform no network actions. The files named by the manifest constitute the upload list; this README, the preparation scripts, manifest, check receipts and review record are local engineering documentation. They are not upload targets.

After an actual supported commit, retrieve every changed target from its returned immutable revision and compare its exact bytes with the manifest. Verify the model and dataset cards and the real static Space in the browser, including all screenshots, download links, keyboard navigation and responsive layout. Record Uploaded, Published and Independently Retrieved separately. Local structure checks do not establish remote rendering or publication.

The complete historical Space rights notice is retained before the new screenshot notice. Artwork and source documents keep their existing terms; application-code licensing does not extend to standalone companion reuse. The original 0.3 preparation files and every existing released artifact remain unchanged.
