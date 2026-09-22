"""Explicit pre-gate refresh of this task's isolated candidate only."""
from pathlib import Path
import json
import hashlib
import shutil

OUT=Path(__file__).resolve().parent
SOURCE=OUT.parents[2]
manifest=json.loads((OUT/'isolated-setup.json').read_text())
target=Path(manifest['isolated_root']).resolve()
assert target.name=='archiosk-planning-composer-01'
assert (target/'.git').is_file()
names=json.loads((OUT/'owned-files.json').read_text())
source_hashes={}
candidate_hashes={}
for name in names:
    source=SOURCE/name
    destination=target/name
    assert destination.resolve().is_relative_to(target)
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,destination)
    source_hashes[name]=hashlib.sha256(source.read_bytes()).hexdigest()
    if name=='services/case_workspace.py':
        text=destination.read_text(encoding='utf-8')
        text=text.replace('                    if cells[-1]["unit"] is None:\n                        cells[-1]["unit"] = cells[-1]["source_location"].get("unit")\n','')
        destination.write_text(text,encoding='utf-8')
    candidate_hashes[name]=hashlib.sha256(destination.read_bytes()).hexdigest()
manifest['repair_owned']=source_hashes
manifest['candidate_hashes']=candidate_hashes
(OUT/'isolated-setup.json').write_text(json.dumps(manifest,indent=2))
print('Candidate refreshed:',len(names),'files; unrelated repair excluded')
