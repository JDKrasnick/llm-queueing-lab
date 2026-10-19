"""Contract tests use a virtual clock, explicitly NOT hardware benchmarks."""

from queueing_lab.model import Catalog
from queueing_lab.runtime import run_live
from test_simulation import tiny


class Clock:
    def __init__(self): self.time=0
    def __call__(self): return self.time
    def sleep(self,seconds): self.time+=seconds


class Session:
    label='test-double-not-hardware'
    def __init__(self,clock,fail=False):
        self.clock=clock; self.active={}; self.submissions=[]; self.fail=fail
    def submit(self,row):
        self.submissions.append((row['id'],self.clock()))
        self.active[row['id']]=[row['class_id'],0]
        return row['id']
    def step(self):
        self.clock.sleep(.02)
        if self.fail: return [(next(iter(self.active)),'failed','injected')]
        out=[]
        for handle,(kind,count) in list(self.active.items()):
            out.append((handle,'token',count))
            self.active[handle][1]+=1
            if count+1==tiny().classes[kind].output_tokens:
                out.append((handle,'finish',None))
        return out
    def close(self,handle): self.active.pop(handle)


def test_native_and_cohort_admission_use_same_offered_clock():
    trace=[dict(id=i,class_id=i%2,arrival=i*.01) for i in range(10)]
    results=[]
    for policy in ('native','fcfs','pressure'):
        clock=Clock(); session=Session(clock)
        result=run_live(session,tiny(),trace,1,policy,Catalog(tiny()),clock,clock.sleep)
        assert result['status']=='observed'
        assert result['metrics']['completed']==10
        assert not session.active
        assert result['backend']=='test-double-not-hardware'
        assert all(stamp>=trace[i]['arrival'] for i,stamp in session.submissions)
        results.append(result)
    assert len({r['trace_sha256'] for r in results})==1


def test_live_failure_retained_and_active_requests_closed():
    clock=Clock(); session=Session(clock,fail=True)
    result=run_live(session,tiny(),[dict(id=0,class_id=0,arrival=0)],1,'native',None,clock,clock.sleep)
    assert result['status']=='failed'
    assert result['error']=='injected'
    assert result['metrics']['unfinished']==1
    assert not session.active


def test_step_crossing_horizon_does_not_publish_post_horizon_tokens():
    clock=Clock(); session=Session(clock)
    result=run_live(session,tiny(),[dict(id=0,class_id=0,arrival=0)],.025,'native',None,clock,clock.sleep)
    assert result['metrics']['completed']==0
    assert len(result['requests'][0]['tokens'])==1
    assert result['metrics']['unfinished']==1
