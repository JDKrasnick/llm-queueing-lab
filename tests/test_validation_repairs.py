"""Regressions from the independent d147a49 audit; all backends here are fake."""
from copy import deepcopy
from types import SimpleNamespace
import json
import shutil
from pathlib import Path

import pytest

from queueing_lab.hardware import GenAISession
from queueing_lab.metrics import summarize
from queueing_lab.runtime import run_live
from queueing_lab.simulator import simulate
from queueing_lab.validation import validate_observation
from queueing_lab.workload import generate,trace_hash
from test_runtime import Clock,Session
from test_simulation import tiny


def test_empty_poisson_observation_is_retained():
    trace=generate(.001,1,20270119)
    assert trace==[]
    clock=Clock();session=Session(clock)
    for result in (simulate(tiny(),trace,1),run_live(session,tiny(),trace,1,'native',clock=clock,sleep=clock.sleep)):
        assert result['metrics']['offered']==result['metrics']['completed']==0
        assert result['metrics']['queue_area_request_s']==0
        assert result['metrics']['restricted_mean_response_s'] is None


def test_zero_completion_and_identical_ttft_clipping():
    rows=[dict(id=0,class_id=0,arrival=0,finish=0,token_times=[0])]
    m=summarize(rows,1,[])
    assert m['queue_area_request_s']==m['per_class']['0']['restricted_mean_response_s']==0
    rows=[dict(id=0,class_id=0,arrival=.1,finish=None,token_times=[1.1])]
    m=summarize(rows,1,[])
    assert m['restricted_mean_ttft_s']==m['per_class']['0']['restricted_mean_ttft_s']==.9


@pytest.mark.parametrize('policy',['native','fcfs','pressure'])
def test_no_new_submission_or_step_after_slow_submit_crosses_horizon(policy):
    from queueing_lab.model import Catalog
    clock=Clock()
    class Slow(Session):
        steps=0
        def submit(self,row):
            handle=super().submit(row);self.clock.sleep(.07);return handle
        def step(self):self.steps+=1;return super().step()
    session=Slow(clock)
    r=run_live(session,tiny(),[dict(id=i,class_id=0,arrival=0) for i in range(4)],.1,policy,Catalog(tiny()),clock,clock.sleep)
    assert len(session.submissions)==2 and session.steps==0
    assert sum(q['admitted'] is None for q in r['requests'])==2
    assert r['metrics']['offered']==4 and not session.active


@pytest.mark.parametrize('failure',['unknown_event','cleanup'])
def test_invalid_events_and_cleanup_errors_are_failed(failure):
    clock=Clock()
    class Broken(Session):
        def step(self):
            self.clock.sleep(.02)
            return [(0,'mystery',None)] if failure=='unknown_event' else []
        def close(self,handle):
            if failure=='cleanup':raise RuntimeError('close failed')
            super().close(handle)
    r=run_live(Broken(clock),tiny(),[dict(id=0,class_id=0,arrival=0)],.1,'native',clock=clock,sleep=clock.sleep)
    assert r['status']=='failed' and r['error']
    assert bool(r['cleanup_errors'])==(failure=='cleanup')


def test_calibration_closes_handle_on_output_mismatch():
    session=GenAISession.__new__(GenAISession);session.config=tiny();closed=[]
    session.submit=lambda row:123
    session.step=lambda:[(123,'finish',None)]
    session.close=closed.append
    with pytest.raises(RuntimeError,match='output count mismatch'):session.cohort((1,0))
    assert closed==[123]


@pytest.mark.parametrize('session_type',[GenAISession,'cache'])
def test_begin_turn_failure_closes_unreturned_request(session_type):
    if session_type=='cache':
        pytest.importorskip('numpy')
        from cache_rl.harness import CacheSession
        session_type=CacheSession
    class Request:
        def begin_turn(self,*args):raise RuntimeError('begin failed')
    class Options:
        def __getattr__(self,key):return lambda *args:None
    request=Request();closed=[];session=session_type.__new__(session_type)
    session.config=tiny();session.prompts={0:[1,2]};session.request_ids={}
    session.og=SimpleNamespace(RequestOptions=Options,TurnOptions=lambda r:Options())
    session.np=SimpleNamespace(asarray=lambda values,**kw:values,int32=int)
    session.engine=SimpleNamespace(create_request=lambda **kw:request)
    session.close=closed.append
    with pytest.raises(RuntimeError,match='begin failed'):session.submit(dict(class_id=0))
    assert closed==[request]


@pytest.mark.parametrize('mutation',['finish','reversed','admission','horizon','policy','config','duplicate','cleanup'])
def test_observation_validator_rejects_auditor_timeline_and_semantics_attacks(mutation):
    clock=Clock();session=Session(clock)
    r=run_live(session,tiny(),[dict(id=0,class_id=0,arrival=0)],1,'native',clock=clock,sleep=clock.sleep)
    validate_observation(r,tiny(),1,'native')
    q=r['requests'][0]
    if mutation=='finish':q['finish']=-1
    elif mutation=='reversed':q['token_times'].reverse()
    elif mutation=='admission':q['admitted']=q['finish']+1
    elif mutation=='horizon':r['horizon_s']=120
    elif mutation=='policy':r['policy']='pressure'
    elif mutation=='config':r['config']['rows']+=1
    elif mutation=='duplicate':r['requests'].append(deepcopy(q))
    elif mutation=='cleanup':r['cleanup_errors']=['injected']
    with pytest.raises(ValueError):validate_observation(r,tiny(),1,'native')


@pytest.mark.parametrize('field,value',[('seed',0),('rate',999),('pattern','bursty')])
def test_hardware_report_binds_workload_to_frozen_plan(tmp_path,field,value):
    from queueing_lab.hardware_report import analyze
    root=Path(__file__).resolve().parents[1]
    shutil.copytree(root/'results/hardware-v1',tmp_path/'copy')
    path=tmp_path/'copy/job-000.json';r=json.loads(path.read_text());r[field]=value;path.write_text(json.dumps(r))
    with pytest.raises(ValueError,match='Workload semantics'):analyze(tmp_path/'copy')


@pytest.mark.parametrize('identity',['wheel','source'])
def test_legacy_report_rejects_zero_build_identities_without_claiming_verification(tmp_path,identity):
    from queueing_lab.hardware_report import analyze
    root=Path(__file__).resolve().parents[1]
    shutil.copytree(root/'results/hardware-v1',tmp_path/'copy')
    path=tmp_path/'copy/baseline-build-provenance.json';record=json.loads(path.read_text())
    if identity=='wheel':record['wheel_sha256']='0'*64
    else:record['baseline_ready']['source']='0'*40
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError,match='Invalid recorded'):analyze(tmp_path/'copy')
