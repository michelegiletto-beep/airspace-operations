# Release 0.3.7 continuation

The unpublished candidate now also addresses the default Windows archive-verification path. The verifier must select a unique isolated workspace, check actual resolved path lengths and run its full installation, CLI, empty API and pytest checks there. An optional work root must be explicit and validated. Test filters, OS settings, operator policy and publication gates are unchanged. Actual final-source receipts are required; the earlier bfc source and Prepared archive remain historical evidence.

# Release 0.3.7-rc.1

This is an unpublished development candidate for safer CLI restore source validation. Original specification acceptance, stable release and operational acceptance remain false.

The earlier restore command can open a missing SQLite backup path as a new empty database, accept its integrity result and report an empty target as restored. The candidate is intended to reject missing or invalid source input before creating source or target files. The existing refusal to overwrite an existing target is retained. The failure concerns creation of an empty missing source and a new empty target, not an ordinary overwrite of an existing database. Source identity, audit-key and operational boundaries remain separate checks.

The published 0.3.6 release remains frozen and retains the earlier behavior. Verify that a backup file already exists and keep independent copies of the database, objects and audit key before using restore there. A success message alone does not establish that expected application records were recovered. The installed primary remains the separately verified 0.3.5 source; this candidate does not promote 0.3.6 into that runtime.

No new test count, current-source CI pass, exact archive installation or publication is claimed by these notes. Those results require distinct actual receipts. No model generation, student training, operational record, aircraft command, permission grant or external communication is added by this metadata preparation.

The selected screenshot is the existing historical 0.3.6 confirmation-review capture. It illustrates a prior engineering conversation with the owned companion, not the 0.3.7 restore repair or a new browser review. Its bytes and reserved artwork rights remain unchanged. There is no new 0.3.7 screenshot.

Previous source, tags, archives, media and publication receipts remain frozen. This candidate requires its own source, security, rights, container, archive and independent-publication gates.
