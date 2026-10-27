# Publication record

The public release is an engineering candidate, not complete acceptance of SPECIFICATION.md. `status.json` records actual publication and independent retrieval. All five listed destinations reached Published and Independently Retrieved; none is merely an expected URL.

The frozen standalone ZIP is 2,090,705 bytes with SHA-256 `a114fa757fe60c9ded044092fac986ce3558cc5ddc5f0c3bd924e9de2caa9d87`. Do not overwrite its published version. Later verification reports and this handover are documentation additions on `main`; the release tag remains at `921996c4db20c449b21dcd03bd21f438911eed62`.

GitHub source was published through the authenticated repository connector, independently cloned, expanded with `python scripts/prepare_corpus.py`, installed with `uv sync --frozen --extra dev` and tested. The exact downloadable ZIP was also extracted into another empty directory and installed/tested. See `release-evidence/github-clean-source-verification.json` and `standalone-archive-verification.json`.

Hugging Face contains the actual trained safetensors artifact and the actual 288-row machine-annotation dataset, with their original lineage and explicit limitations. Public unauthenticated downloads were compared with local hashes. The model is experimental and unpromoted. No private operational data or cached third-party weights were uploaded.

The existing public System Lab site was updated through its source workflow in an isolated clean checkout. Only the new project page, its CSS/download assets and one homepage link were added. The official build passed, source commit `bb9ffcd968917e28ab085bcf098abeb417fa8147` was pushed, version 94 was saved with its matching locally packaged build, and the native deployment returned `succeeded`. The audience remained public. The canonical project page and identical ZIP were then retrieved without authentication. Run `.venv/Scripts/python.exe scripts/verify_site_publication.py` to repeat those public checks.

Publications expose documentation and software downloads. They do not publish an operational customer instance, grant any flight permission or close the implementation/domain-review gates. No new paid service was purchased. Existing account identity and ownership were checked before publication; service credentials were passed transiently and excluded from source, logs and release artifacts.
