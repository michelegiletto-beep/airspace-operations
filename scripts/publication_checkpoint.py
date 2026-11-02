"""Bind current publication aliases to completed, version-matched receipts.

This pure function performs no network, filesystem or publication actions.
Historical snapshots are retained exactly; development state is caller-owned.
"""
from copy import deepcopy
import re


def reconcile_current_publication(status, evidence, paths):
    """Return reconciled current fields, rejecting incomplete or mixed receipts."""
    result = deepcopy(status)
    release = status["release"]
    source = status["published_archive"]["source_commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("A frozen source identity is required")
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    destinations = {row["destination"]: row for row in result["destinations"]}
    for name in ("GitHub candidate release source", "GitHub tagged candidate release"):
        row = destinations[name]
        require(row["release"] == release and row["commit"] == source
                and row["state"] == "Independently Retrieved",
                "GitHub aliases must match the frozen published release")
    site = destinations["System Lab project dossier revision"]
    native, public = evidence["site_native"], evidence["site_public"]
    saved, deployed = native["saved"], native["deployed"]
    require(public["success"] is True and public["state"] == "Independently Retrieved"
            and public["version"] == release and public["release_source_commit"] == source,
            "Site receipt must verify the current frozen release")
    require(saved["id"] == deployed["version_id"] and deployed["status"] == "succeeded"
            and saved["project_id"] == deployed["project_id"] == site["project_id"]
            and saved["version_number"] == public["version_number"] == site["version"]
            and saved["source"]["commit_sha"] == public["site_source_commit"] == site["source_commit"]
            and deployed["id"] == public["deployment_id"] == site["deployment_id"],
            "Saved, deployed and public Site identities must agree")
    require(public["summary"]["expected"] == public["summary"]["verified"]
            == public["summary"]["http_200"], "All Site resources must verify")
    site.update(saved_version_id=saved["id"], prepared_source_commit=public["site_source_commit"],
                remote_source_commit=public["site_source_commit"],
                prior_release=site["previous_verified"]["release"])
    manifest = evidence["hub_manifest"]
    require(manifest["application_version"] == release and manifest["application_source"] == source,
            "Hub pack must match the current frozen release")
    for kind, name in (("model", "Hugging Face model presentation"),
                       ("dataset", "Hugging Face dataset presentation"),
                       ("space", "Hugging Face recorded evaluation Space")):
        row, receipt = destinations[name], evidence["hub"][kind]
        expected = {item["target"]: (item["bytes"], item["sha256"])
                    for item in manifest["files"] if item["repo_type"] == kind}
        actual = {item["target"]: (item["bytes"], item["sha256"])
                  for item in receipt["changed_files"]}
        require(receipt["success"] is True and receipt["state"] == "Independently Retrieved"
                and receipt["head"] == row["revision"]
                and receipt["expected_parent"] == manifest["prior_revisions"][kind]
                and receipt["direct_parent"]["verified"] is True
                and receipt["direct_parent"]["parent"] == receipt["expected_parent"]
                and receipt["only_reviewed_targets_and_exact_provider_LFS_entries_changed"] is True
                and receipt["repo_type"] == kind
                and {item["repo_id"] for item in manifest["files"] if item["repo_type"] == kind}
                    == {receipt["repository"]}
                and row["url"] == receipt["url"] and row["release"] == release
                and row["previous_verified"]["revision"] == receipt["expected_parent"]
                and len(receipt["changed_files"]) == len(actual)
                and all(item["matches_reviewed_manifest_and_local_source"] is True
                        for item in receipt["changed_files"])
                and actual == expected and bool(expected),
                "Hub targets, parent and current revision must verify")
        row.update(current_published_revision=receipt["head"], prepared_application_version=release,
                   prepared_files_manifest=paths["hub_manifest"], preparation_evidence=paths["hub_publication"],
                   prior_release=row["previous_verified"]["release"], prior_revision=receipt["expected_parent"])
    space = destinations["Hugging Face recorded evaluation Space"]
    live = evidence["space_live"]
    require(live["success"] is True and live["state"] == "Independently Retrieved"
            and live["head"] == space["revision"] and live["host"] == space["host"]
            and live["metadata"]["runtime_stage"] == "RUNNING"
            and live["negative_comparisons"]["count"] == 4
            and live["verified_hosting_additions"]["all_remaining_authored_bytes_exact"] is True
            and bool(live["files"])
            and len({item["path"] for item in live["files"]}) == len(live["files"])
            and all(item["status"] == 200 and item["exact_authored_manifest_match"] is True
                    for item in live["files"]), "The current live Space must verify independently")
    space["live_host_evidence"] = paths["space_live"]
    document = evidence["documentation"]
    require(document["success"] is True and document["state"] == "Independently Retrieved"
            and re.fullmatch(r"[0-9a-f]{40}", document["github_main"])
            and document["exact"] == document["expected"] == len(document["files"])
            and document["exact"] > 0
            and len({item["path"] for item in document["files"]}) == len(document["files"])
            and all(item["status"] == 200 and item["exact"] is True for item in document["files"]),
            "Documentation publication requires exact independently retrieved files")
    checkpoint = {"state": "Independently Retrieved", "published": True,
                  "commit": document["github_main"], "exact_files": document["exact"],
                  "receipt": paths["documentation"],
                  "scope": "Published documentation and evidence; frozen software source remains " + source}
    result["documentation_checkpoint"] = checkpoint
    result["publication_metadata_checkpoint"] = dict(checkpoint,
        source_commit=source, scope="Previously published metadata payload; any new corrective payload requires its own later publication receipt")
    return result
