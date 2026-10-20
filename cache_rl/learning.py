"""Episodic REINFORCE on actual native Engine scheduling trajectories.

Actions are sampled by the C++ actor each scheduling step, with duplicate
rankings masked. Training consumes its logged state/probability/action tuples.
The scalar terminal return penalizes response, TTFT, streaming gaps and failure.
This is policy-gradient RL, not an oracle-label classifier or a simulator fit.
"""
import math
import numpy as np


def reward(result,reference):
    if reference['status']!='observed' or reference['metrics']['completed']!=reference['metrics']['offered']:
        raise ValueError('Incomplete training reference; no valid paired reward')
    if result['status']!='observed' or result['metrics']['completed']!=result['metrics']['offered']:
        return -10.0
    reference_outputs={r['id']:r['tokens'] for r in reference['requests']}
    if any(r['tokens']!=reference_outputs[r['id']] for r in result['requests']):return -10.0
    m,b=result['metrics'],reference['metrics']
    terms=[]
    for key,weight in [('restricted_mean_response_s',.4),('restricted_mean_ttft_s',.4),('observed_p99_gap_s',.2)]:
        if m[key] is None or b[key] is None:return -10.0
        ratio=m[key]/max(b[key],1e-6)
        terms.append(weight*math.log(max(ratio,1e-6)))
    # Completed fixed workloads: final completion time is the throughput proxy;
    # fixed-horizon completions/s would be identical once all64 finish.
    finish=max(r['finish'] for r in result['requests'])
    base_finish=max(r['finish'] for r in reference['requests'])
    penalty=sum(max(0,m[k]/max(b[k],1e-6)-1.02) for k in
                ['restricted_mean_response_s','restricted_mean_ttft_s','observed_p99_gap_s'])
    return float(np.clip(-sum(terms)-.2*math.log(finish/base_finish)-2*penalty,-10,2))


def policy_gradient(trajectory,advantage):
    gradient=np.zeros((3,8),dtype=float)
    for step in trajectory:
        probabilities=np.asarray(step['probability'],dtype=float)
        state=np.asarray(step['state'],dtype=float)
        if probabilities.shape!=(3,) or state.shape!=(8,) or not np.isfinite(state).all():
            raise ValueError('Invalid native actor trajectory')
        if not np.isclose(probabilities.sum(),1) or np.any(probabilities<0):raise ValueError('Invalid probabilities')
        action=step['action']
        if not step['mask'][action] or probabilities[action]<=0:raise ValueError('Invalid selected action')
        score=-probabilities;score[action]+=1
        gradient+=np.outer(score,state)
    # Sum is the episodic score-function gradient. Divide by a fixed constant,
    # not trajectory length (an action-dependent divisor would change objective).
    return float(advantage)*gradient/64.0


def update(weights,trajectories,returns,step_size=.15):
    if len(trajectories)!=len(returns) or len(returns)<2:raise ValueError('Need a rollout batch')
    result=np.asarray(weights,dtype=float).copy()
    gradient=np.zeros_like(result)
    # Leave-one-out baseline is independent of this trajectory's sampled actions.
    for i,(trajectory,value) in enumerate(zip(trajectories,returns,strict=True)):
        baseline=(sum(returns)-value)/(len(returns)-1)
        gradient+=policy_gradient(trajectory,value-baseline)/len(returns)
    norm=np.linalg.norm(gradient)
    if norm>1:gradient/=norm
    result+=step_size*gradient
    return np.clip(result,-8,8),dict(gradient_norm=float(norm),mean_return=float(np.mean(returns)))
