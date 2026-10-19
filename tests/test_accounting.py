import json
from pathlib import Path
import zipfile

import pytest

from queueing_lab.metrics import summarize
from queueing_lab.provenance import manifest, snapshot
from queueing_lab.simulator import backlog_samples


def area_by_independent_event_sweep(rows,horizon,first=False):
    events=[]
    for r in rows:
        events.append((r['arrival'],1))
        finish=(r['token_times'][0] if r['token_times'] else None) if first else r['finish']
        if finish is not None and finish<=horizon:
            events.append((finish,-1))
    count=0;last=0;area=0
    for t,change in sorted(events):
        area+=(t-last)*count;count+=change;last=t
    return area+(horizon-last)*count


def test_restricted_response_and_ttft_match_event_sweep_including_censored():
    rows=[dict(id=0,class_id=0,arrival=.1,finish=.5,token_times=[.3,.4,.5]),
          dict(id=1,class_id=0,arrival=.2,finish=None,token_times=[.7,.8]),
          dict(id=2,class_id=1,arrival=.5,finish=None,token_times=[])]
    result=summarize(rows,1,backlog_samples(rows,1,.1))
    assert result['queue_area_request_s']==pytest.approx(area_by_independent_event_sweep(rows,1))
    assert result['first_token_queue_area_request_s']==pytest.approx(area_by_independent_event_sweep(rows,1,True))
    assert result['restricted_mean_ttft_s']==pytest.approx((.2+.5+.5)/3)
    assert result['ttft_censored']==1
    assert result['per_class']['1']['unfinished']==1
    assert result['per_class']['1']['restricted_mean_ttft_s']==.5


def test_source_snapshot_verifies_bytes_and_rejects_midrun_edits(tmp_path):
    (tmp_path/'source.py').write_text('a = 1\n')
    source=manifest(tmp_path)
    snapshot(tmp_path,tmp_path/'source.zip',source)
    with zipfile.ZipFile(tmp_path/'source.zip') as archive:
        assert archive.read('source.py')==b'a = 1\n'
    (tmp_path/'source.py').write_text('a = 2\n')
    with pytest.raises(RuntimeError): snapshot(tmp_path,tmp_path/'changed.zip',source)


def test_hardware_module_import_has_no_optional_dependency_side_effects():
    import queueing_lab.hardware
    assert queueing_lab.hardware.GenAISession.label=='onnxruntime-genai-engine'
