from pathlib import Path,PurePosixPath
from datetime import datetime,timezone
import hashlib,json,re,zipfile
root=Path.cwd();folder=root/'release/0.3.0-rc.1';evidence=root/'release-evidence/v0.3.0-rc.1'
sha=lambda b:hashlib.sha256(b).hexdigest()
archive=folder/'System-Lab-Airspace-Operations-0.3.0-rc.1.zip';archive_sha=sha(archive.read_bytes())
provenance=json.loads((folder/'RELEASE_PROVENANCE.json').read_bytes());gate=json.loads((folder/'release-gates.json').read_bytes());ci=json.loads((folder/'ci-verification.json').read_bytes());clean=json.loads((folder/'standalone-archive-verification.json').read_bytes())
assert provenance['source_commit']==ci['commit']=='331b6e220fec5254c4c2f167cab3ad86d8905456'
assert provenance['version']==gate['version']==clean['version']=='0.3.0-rc.1'
assert provenance['baseline_sha256']=='43755041cbfa555158b51979de4c726bf52f7e82dc113e840c1488d974ba9b30'
assert provenance['gates']==gate and gate['engineering_checks_passed'] and all(gate['checks'].values())
assert not gate['stable_release_allowed'] and not gate['operational_acceptance']
assert ci['conclusion']=='success' and ci['run_id']==40803017486 and gate['external_ci']['verified']
assert clean['success'] and clean['installation_exit']==clean['test_suite']['exit_code']==0 and clean['archive_sha256']==archive_sha
assert (folder/'SHA256SUMS.txt').read_text().strip()==archive_sha+'  '+archive.name
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 names=z.namelist();assert len(names)==len(set(names))
 prefix='airspace-operations/'
 assert all(n.startswith(prefix) and not n.endswith('/') for n in names)
 members={n[len(prefix):]:z.read(n) for n in names}
 assert set(members)==set(provenance['files'])|{'RELEASE_PROVENANCE.json'}
 assert all(sha(members[n])==s for n,s in provenance['files'].items())
 assert members['RELEASE_PROVENANCE.json']==(folder/'RELEASE_PROVENANCE.json').read_bytes()
 assert all(sha(members[n])==s for n,s in ci['local_software_input_hashes'].items())
 attachments=['LICENSE','SBOM.cdx.json','THIRD_PARTY_NOTICES.md']
 assert all(members[n]==(folder/n).read_bytes() for n in attachments)
 assert members['release-evidence/v0.3.0-rc.1/release-gates.json']==(folder/'release-gates.json').read_bytes()
 assert members['release-evidence/v0.3.0-rc.1/ci-verification.json']==(folder/'ci-verification.json').read_bytes()
 media=[]
 for n in ['publication/media/v0.3/desktop-companion.jpg','publication/media/v0.3/mobile-companion.jpg']:
  assert members[n]==(root/n).read_bytes()
  media.append({'path':n,'bytes':len(members[n]),'sha256':sha(members[n]),'matches_downloaded_archive':True})
 report={'checked_at':datetime.now(timezone.utc).isoformat(),'archive_sha256':archive_sha,'source_commit':provenance['source_commit'],'archive_member_count':len(members),'manifest_hashed_files':len(provenance['files']),'total_uncompressed_bytes':sum(len(b) for b in members.values()),'all_manifest_digests_match':True,'exact_manifest_members':True,'ci_source_hash_count':len(ci['local_software_input_hashes']),'ci_source_hashes_match_archive':True,'zip_crc_valid':True,'attached_source_license_sbom_notices_and_gate_bytes_match_archive':True,'baseline_integrity':True,'receipt_binds_exact_archive':True,'clean_install_report_actual_summary':re.findall(r'\d+ passed, \d+ skipped[^\n]*',clean['test_suite']['stdout']),'stable_release_allowed':False,'operational_acceptance':False,'media':media,'scope':'Independent byte and receipt validation of an already published candidate. Existing clean-install execution is the CI run, not a fresh local execution. No test results or professional review are inferred from digest checks.'}
(evidence/'cycle-20261030-archive-integrity.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
