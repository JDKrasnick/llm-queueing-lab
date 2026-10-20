"""Retain the source, wheels and build record used for this GPU repeat."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import zipfile


def main():
    root=Path('/content')
    paths={
        'baseline-source.tar.gz':root/'planner-validation/planner-source-baseline.tar.gz',
        'baseline.whl':next((root/'planner-validation').glob('baseline-*.whl')),
        'candidate.whl':next((root/'cache-coalesce-build').glob('*.whl')),
        'baseline-ready.json':root/'planner-validation/baseline-ready.json',
        'bootstrap.py':root/'planner-validation/planner-bootstrap.py',
        'build.log':root/'cache-recovery.log',
    }
    manifest={'source_revision':'3d0d6eb1327a959c54f2a41f6741ab9414e50286',
              'record_type':'Retained build inputs and outputs; not a hermetic build attestation',
              'python':sys.version,'files':{}}
    archive=root/'cache-build-evidence.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name,path in paths.items():
            data=path.read_bytes();manifest['files'][name]=hashlib.sha256(data).hexdigest();z.writestr(name,data)
        z.writestr('manifest.json',json.dumps(manifest,indent=2))
        for command in (['nvidia-smi'],['cmake','--version'],['g++','--version']):
            z.writestr(command[0]+'.txt',subprocess.check_output(command,text=True))
    (root/'cache-coalesce-build/build-evidence.json').write_text(json.dumps({
        'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'manifest':manifest},indent=2))
    print('BUILD_EVIDENCE_READY',archive.stat().st_size,hashlib.sha256(archive.read_bytes()).hexdigest(),flush=True)


if __name__=='__main__':main()
