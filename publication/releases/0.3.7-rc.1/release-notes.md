# Release 0.3.7-rc.1

This engineering candidate repairs SQLite backup source validation and the default Windows archive-verification workspace. Original specification acceptance, stable release and operational acceptance remain false.

Missing or invalid SQLite backup input is rejected before target creation. Existing targets remain protected. Keep independent copies of the database, objects and audit key and verify expected records after restoration.

The archive verifier selects a unique isolated temporary directory on Windows, checks resolved path lengths and verifies source hashes before running the full installation, CLI, empty API and test suite. An explicit work root is validated. Test filters, OS settings, operator policy and publication gates are unchanged.

Actual source-specific results are attached separately. This release does not promote the installed primary, add operational records, run new model generation or training, or grant operational permissions.

The selected release screenshot is the historical 0.3.6 confirmation-review capture. It illustrates a prior engineering conversation with the owned companion; it is not a new restore validation or flight record. Artwork rights and screenshot bytes are unchanged.

Previous source, tags, archives, media and publication receipts remain available. Complete European coverage, stable release and operational acceptance are not claimed.
