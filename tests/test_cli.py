import json
from pathlib import Path
import subprocess
import sys


def test_capacity_cli_and_hardware_configuration(tmp_path):
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,'-m','queueing_lab','capacity'],cwd=root,capture_output=True,text=True,check=True)
    certificate=json.loads(result.stdout)
    assert certificate['requests_s']>0
    assert certificate['monotone']
    path=tmp_path/'hardware.json'
    subprocess.run([sys.executable,'-m','queueing_lab','hardware-config',str(path)],cwd=root,check=True)
    config=json.loads(path.read_text())
    assert config['block_size']==256
    assert config['rows']==4
