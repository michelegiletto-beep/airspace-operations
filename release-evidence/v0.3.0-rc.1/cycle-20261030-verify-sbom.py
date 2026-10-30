from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.metadata,json,urllib.request
import jsonschema
root=Path.cwd();folder=root/'release/0.3.0-rc.1';seen={}
revision='e833d732337dd33aceb45ff1991f896796f1e5e7'
op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def retrieve(url):
 from urllib.parse import urlsplit
 parts=urlsplit(url)
 if parts.hostname!='cyclonedx.org' or not parts.path.startswith('/schema/') or Path(parts.path).name!=parts.path.split('/')[-1]:raise ValueError('Schema scope mismatch')
 actual='https://raw.githubusercontent.com/CycloneDX/specification/'+revision+'/schema/'+Path(parts.path).name
 with op.open(urllib.request.Request(actual,headers={'User-Agent':'System-Lab-Publication-Verifier/0.3'}),timeout=20) as response:data=response.read(2000001)
 if len(data)>2000000:raise ValueError('Schema exceeds bound')
 seen[actual]=hashlib.sha256(data).hexdigest();return json.loads(data)
schema=retrieve('https://cyclonedx.org/schema/bom-1.6.schema.json')
data=(folder/'SBOM.cdx.json').read_bytes();document=json.loads(data)
resolver=jsonschema.RefResolver.from_schema(schema,handlers={'http':retrieve,'https':retrieve})
jsonschema.Draft7Validator(schema,resolver=resolver).validate(document)
assert document['metadata']['component']['version']=='0.3.0-rc.1'
report={'checked_at':datetime.now(timezone.utc).isoformat(),'valid':True,'artifact':'release/0.3.0-rc.1/SBOM.cdx.json','sbom_sha256':hashlib.sha256(data).hexdigest(),'components':len(document['components']),'validator':'jsonschema '+importlib.metadata.version('jsonschema'),'official_schema_revision':revision,'official_schema_sha256':seen,'scope':'Formal CycloneDX1.6 JSON schema validation of the exact anonymously downloaded SBOM, not licence clearance or vulnerability assessment'}
(root/'release-evidence/v0.3.0-rc.1/cycle-20261030-sbom-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
