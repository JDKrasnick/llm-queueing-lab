from dataclasses import replace
import itertools
import math
import random

import pytest

from queueing_lab.model import Catalog, Config, RequestClass, token_offsets
from queueing_lab.policies import pop_action, select


def test_reservation_counts_declared_bound_not_realized_output():
    config=Config()
    assert config.blocks_for(0)==13
    assert config.blocks_for(1)==4
    assert not config.feasible((3,0))
    assert config.feasible((0,8))
    with pytest.raises(ValueError):
        replace(config,blocks=3)


def test_all_catalogs_downward_closed_monotone_and_token_consistent():
    rng=random.Random(921)
    for _ in range(20):
        config=replace(Config(),blocks=rng.choice((16,32,64)),rows=rng.randint(1,8),
                       decode_row_s=rng.random()*.002,attention_token_s=rng.random()*.000001)
        catalog=Catalog(config)
        assert catalog.monotone()
        for action in catalog.actions:
            paths,duration=token_offsets(config,action)
            assert duration>0
            for i,tokens in paths.items():
                assert len(tokens)==config.classes[i].output_tokens
                assert tokens==sorted(tokens)
                assert tokens[-1]<=duration
            for child in itertools.product(*(range(n+1) for n in action)):
                if sum(child):
                    assert config.feasible(child)


def test_capacity_certificate_against_dense_independent_time_mixtures():
    catalog=Catalog(Config())
    for mix in ((.5,.5),(.1,.9),(.8,.2)):
        certificate=catalog.capacity(mix)
        a,b=tuple(certificate['action_a']),tuple(certificate['action_b'])
        w=certificate['time_fraction_a']
        r=catalog.rates()
        actual=[w*r[a][i]+(1-w)*r[b][i] for i in range(2)]
        assert min(actual[i]/mix[i] for i in range(2))==pytest.approx(certificate['requests_s'])
        # Every vertex/pair on a dense grid must lie at/below the exact certificate.
        for x,y in itertools.product(r.values(),repeat=2):
            for fraction in (0,.1,.2,.4,.6,.8,.9,1):
                rate=min((fraction*x[i]+(1-fraction)*y[i])/mix[i] for i in range(2))
                assert rate<=certificate['requests_s']+1e-9


def test_pressure_exact_argmax_and_bounded_truncation_loss():
    catalog=Catalog(Config())
    for q in itertools.product(range(0,17),repeat=2):
        if sum(q)==0: continue
        waiting=[dict(id=i*100+j,class_id=i,arrival=j*.01) for i,n in enumerate(q) for j in range(n)]
        action=select('pressure',waiting,catalog)
        score=lambda a:sum(q[i]*n for i,n in enumerate(a))/catalog.durations[a]
        assert score(action)==max(score(a) for a in catalog.actions if all(n<=q[i] for i,n in enumerate(a)))
        unrestricted=max(score(a) for a in catalog.actions)
        bound=len(q)*catalog.config.rows**2/min(catalog.durations.values())
        assert unrestricted-score(action)<=bound+1e-8


def test_fcfs_skip_unfittable_and_stable_per_class_order():
    catalog=Catalog(Config())
    rows=[dict(id=i,arrival=0,class_id=k) for i,k in enumerate((0,0,0,1,1,1,1))]
    action=select('fcfs',rows,catalog)
    assert action==(2,1)
    selected=pop_action(rows,action)
    assert [r['id'] for r in selected]==[0,1,3]
    assert [r['id'] for r in rows]==[2,4,5,6]


def test_reject_invalid_and_incomplete_service_tables():
    with pytest.raises(ValueError): Catalog(Config(),{})
    with pytest.raises(ValueError): Config(setup_s=float('nan'))
    with pytest.raises(ValueError): RequestClass('bad',1,5,4)
    with pytest.raises(ValueError): Catalog(Config()).capacity((1,0))
