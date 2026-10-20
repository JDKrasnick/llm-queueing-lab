from pathlib import Path
import shutil
import subprocess

import pytest


def test_native_cache_order_decode_priority_age_and_shared_block_charge(tmp_path):
    compiler=shutil.which('c++')
    if not compiler:pytest.skip('C++ compiler unavailable')
    root=Path(__file__).resolve().parents[1]
    binary=tmp_path/'cache-policy-test'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-I',str(root/'native'),
                    str(root/'native/test_cache_policy.cpp'),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)


def test_native_coalescing_exact_match_residents_age_and_leader_removal(tmp_path):
    compiler=shutil.which('c++')
    if not compiler:pytest.skip('C++ compiler unavailable')
    root=Path(__file__).resolve().parents[1]
    binary=tmp_path/'coalescing-test'
    subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-I',str(root/'native'),
                    str(root/'native/test_coalescing.cpp'),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)


def test_reinforce_gradient_matches_independent_finite_difference():
    np=pytest.importorskip('numpy')
    from cache_rl.learning import policy_gradient
    rng=np.random.default_rng(1041)
    for mask in ([1,1,1],[1,0,1],[1,1,0]):
        weights=rng.normal(size=(3,8))*.2;state=rng.normal(size=8)
        def logprob(w,action):
            logits=w@state;logits=np.where(mask,logits,-np.inf)
            return logits[action]-np.log(np.exp(logits).sum())
        logits=weights@state;probabilities=np.exp(np.where(mask,logits,-np.inf));probabilities/=probabilities.sum()
        action=next(i for i,v in reversed(list(enumerate(mask))) if v)
        step=dict(action=action,state=state.tolist(),probability=probabilities.tolist(),mask=mask)
        gradient=policy_gradient([step],.7)*64
        for a in range(3):
            for k in range(8):
                plus=weights.copy();minus=weights.copy();plus[a,k]+=1e-6;minus[a,k]-=1e-6
                numeric=.7*(logprob(plus,action)-logprob(minus,action))/2e-6
                assert gradient[a,k]==pytest.approx(numeric,abs=2e-8)


def test_learning_rejects_invalid_actor_masks():
    pytest.importorskip('numpy')
    from cache_rl.learning import policy_gradient
    with pytest.raises(ValueError):policy_gradient([dict(action=1,state=[1]*8,probability=[1,0,0],mask=[1,0,0])],1)


def test_rl_reward_rejects_fast_incorrect_and_incomplete_output():
    pytest.importorskip('numpy')
    from copy import deepcopy
    from cache_rl.learning import reward
    baseline=dict(status='observed',metrics=dict(completed=1,offered=1,
        restricted_mean_response_s=1.,restricted_mean_ttft_s=1.,observed_p99_gap_s=.1),
        requests=[dict(id=0,tokens=[1,2],finish=2.)])
    faster=deepcopy(baseline)
    for key in ('restricted_mean_response_s','restricted_mean_ttft_s','observed_p99_gap_s'):faster['metrics'][key]*=.8
    faster['requests'][0]['finish']=1.6
    assert reward(faster,baseline)>0
    faster['requests'][0]['tokens']=[9,9]
    assert reward(faster,baseline)==-10
    incomplete=deepcopy(baseline);incomplete['metrics']['completed']=0
    assert reward(incomplete,baseline)==-10
    with pytest.raises(ValueError):reward(baseline,incomplete)

