import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import pytest

from queueing_lab.hardware_report import analyze


ROOT=Path(__file__).resolve().parents[1]


def test_frozen_model_source_archive_matches_every_prerun_hash():
    directory=ROOT/'results/screen-v2'
    if not directory.exists(): pytest.skip('Full experiment archive not installed with the wheel')
    manifest=json.loads((directory/'plan.json').read_text())['provenance']['files']
    with zipfile.ZipFile(directory/'source-snapshot.zip') as archive:
        assert set(archive.namelist())==set(manifest)
        for name,expected in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest()==expected


@pytest.mark.parametrize('corruption',['binary','trace','tokens'])
def test_actual_evidence_rejects_identity_and_event_corruption(tmp_path,corruption):
    original=ROOT/'results/hardware-v1'
    if not original.exists(): pytest.skip('Actual-engine evidence not installed with the wheel')
    dest=tmp_path/'evidence'
    dest.mkdir()
    for path in original.glob('*.json'):
        shutil.copy2(path,dest/path.name)
    file=dest/'job-000.json'
    result=json.loads(file.read_text())
    if corruption=='binary':result['provenance']['package_libraries']['rogue.so']='bad'
    elif corruption=='trace':result['requests'][0]['arrival']+=.001
    else:result['requests'][0]['tokens'][0]+=1
    file.write_text(json.dumps(result))
    with pytest.raises(ValueError): analyze(dest)
