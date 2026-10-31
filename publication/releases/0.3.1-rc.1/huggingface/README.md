# Hugging Face presentation update

State: **Prepared**. No upload or publication occurred. The existing supported browser session is signed out and no configured Hub token is available. This directory supplies a reviewable presentation update for the three existing Magic51 repositories. It does not create a model, dataset, Space or account.

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
