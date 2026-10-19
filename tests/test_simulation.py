from dataclasses import replace
import math

import pytest

from queueing_lab.metrics import quantile
from queueing_lab.model import Config, RequestClass
from queueing_lab.network import simulate_network
from queueing_lab.simulator import simulate
from queueing_lab.workload import generate, trace_hash, validate_trace


def tiny():
    return Config(classes=(RequestClass('a',1,2,2),RequestClass('b',2,3,3)),rows=2,blocks=8,
                  block_size=4,setup_s=.1,prefill_token_s=.1,decode_step_s=.1,decode_row_s=.01,attention_token_s=0)


def test_single_request_hand_computed_first_and_final_tokens():
    result=simulate(tiny(),[dict(id=0,arrival=.25,class_id=0)],2)
    row=result['requests'][0]
    assert row['token_times']==pytest.approx([.45,.56])
    assert row['finish']==pytest.approx(.56)
    assert result['metrics']['queue_area_request_s']==pytest.approx(.31)
    assert result['metrics']['unfinished']==0


def test_arrivals_during_service_and_right_censoring_are_not_dropped():
    trace=[dict(id=i,arrival=.001*i,class_id=i%2) for i in range(20)]
    result=simulate(tiny(),trace,.3,'pressure',sample_period=.01)
    assert result['metrics']['offered']==20
    assert result['metrics']['unfinished']+result['metrics']['completed']==20
    assert result['metrics']['ttft_censored']>0
    assert result['backlog'][-1][1]==result['metrics']['unfinished']
    assert all(t<=.3 for r in result['requests'] for t in r['token_times'])
    expected=sum(min(r['finish'] or .3,.3)-r['arrival'] for r in result['requests'])
    assert result['metrics']['queue_area_request_s']==expected


def test_poisson_offered_trace_identical_across_policies_and_no_future_admission():
    for pattern in ('poisson','bursty','regular','phase'):
        trace=generate(20,10,122,pattern=pattern)
        results=[simulate(tiny(),trace,10,p) for p in ('fcfs','pressure')]
        assert results[0]['trace_sha256']==results[1]['trace_sha256']==trace_hash(trace)
        for result in results:
            assert len(result['requests'])==len(trace)
            assert all(r['admitted'] is None or r['admitted']>=r['arrival'] for r in result['requests'])
            for cohort in result['cohorts']:
                assert tiny().feasible(cohort['action'])


def test_fork_join_never_releases_join_before_both_branches_finish():
    trace=generate(4,5,723)
    for policy in ('fcfs','pressure','backpressure'):
        result=simulate_network(tiny(),trace,5,policy)
        tasks={(r['root_id'],r['node']):r for r in result['tasks']}
        for job in result['jobs']:
            root=job['id']
            if (root,3) in tasks:
                assert tasks[root,3]['arrival']>=max(tasks[root,1]['finish'],tasks[root,2]['finish'])
            if job['finish'] is not None:
                assert job['completed_nodes']==[0,1,2,3]
                assert job['finish']==tasks[root,3]['finish']
        assert all(min(r['in_service'])>=0 for r in result['history'])
        assert result['metrics']['offered_roots']==len(trace)


def test_invalid_networks_and_traces_fail_early():
    trace=[dict(id=0,arrival=0,class_id=0)]
    with pytest.raises(ValueError): simulate_network(tiny(),trace,1,edges=((1,),(0,)))
    with pytest.raises(ValueError): validate_trace(trace*2,2)
    with pytest.raises(ValueError): generate(0,10,1)
    with pytest.raises(ValueError): generate(10,float('inf'),1)
    assert quantile([],0.99) is None
    assert quantile([1,2,3],.5)==2


def test_unseen_future_arrivals_cannot_change_earlier_decisions():
    prefix=[dict(id=i,class_id=i%2,arrival=.1*i) for i in range(8)]
    futures=[prefix+[dict(id=100,class_id=k,arrival=3)] for k in (0,1)]
    for policy in ('fcfs','pressure'):
        results=[simulate(tiny(),trace,5,policy) for trace in futures]
        early=[[c for c in r['cohorts'] if c['start']<3] for r in results]
        assert early[0]==early[1]
