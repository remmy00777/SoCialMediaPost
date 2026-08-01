#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"
mkdir -p security
python3 - <<'PY'
import json,re
from pathlib import Path
p=Path('backend/pyproject.toml').read_text(); deps=[]
inside=False
for line in p.splitlines():
    if line.strip()=='dependencies = [': inside=True; continue
    if inside and line.strip()==']': break
    if inside and line.strip().startswith('"'):
        raw=line.strip().strip(',').strip('"'); name=re.split(r'[<>=!~\[]',raw,1)[0]; deps.append({'type':'library','name':name,'version_constraint':raw[len(name):]})
node=json.loads(Path('frontend/package.json').read_text())
for group in ('dependencies','devDependencies','optionalDependencies'):
    for name,version in node.get(group,{}).items(): deps.append({'type':'library','name':name,'version_constraint':version,'scope':group})
sbom={'bomFormat':'CycloneDX','specVersion':'1.6','version':1,'metadata':{'component':{'type':'application','name':'SoCialMediaPost Studio','version':'0.1.0'}},'components':deps}
Path('security/sbom.cdx.json').write_text(json.dumps(sbom,indent=2)+'\n')
print('security/sbom.cdx.json')
PY
