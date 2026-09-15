"""Freeze candidate and necessary retained dependencies, not unrelated work."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

SOURCE = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
TARGET = Path(r'C:\Users\info\AppData\Local\Temp\archiosk-planning-composer-01')
head = subprocess.check_output(['git','rev-parse','HEAD'], cwd=SOURCE, text=True).strip()
assert not TARGET.exists(), 'Do not overwrite an existing qualification tree'
subprocess.run(['git','worktree','add','--detach',str(TARGET),head],cwd=SOURCE,check=True)
copied = {}

def copy(relative):
    src, dst = SOURCE / relative, TARGET / relative
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    assert digest == hashlib.sha256(dst.read_bytes()).hexdigest()
    copied[relative] = digest

names = json.loads((OUT/'owned-files.json').read_text())
for name in sorted(names): copy(name)
owned = dict(copied)
# The workspace also contains an unrelated table-binding repair. Preserve it
# there; this candidate contains only the Planning snapshot field addition.
p=TARGET/'services/case_workspace.py'
s=p.read_text(encoding='utf-8')
s=s.replace('                    if cells[-1]["unit"] is None:\n                        cells[-1]["unit"] = cells[-1]["source_location"].get("unit")\n','')
p.write_text(s,encoding='utf-8')
candidate_hashes={n:hashlib.sha256((TARGET/n).read_bytes()).hexdigest() for n in names}
assets = json.loads((SOURCE/'docs/records/assembler-closeout-05c/asset-audit.json').read_text())['asset_files']
for name, digest in assets.items():
    relative = 'static/nipigon/' + name
    assert hashlib.sha256((SOURCE/relative).read_bytes()).hexdigest() == digest
    copy(relative)
report = dict(candidate_hashes=candidate_hashes, head=head, isolated_root=str(TARGET), repair_owned=owned,
              copied_dependencies_and_assets=copied,
              provisioning='Existing hash-verified Nipigon test assets; no new retrieval',
              shared_state=subprocess.check_output(['git','status','--short'],cwd=SOURCE,text=True),
              expected_runtime_seconds=720, anomaly_threshold_seconds=900)
(OUT/'isolated-setup.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(dict(head=head, files=len(copied), root=str(TARGET))))
