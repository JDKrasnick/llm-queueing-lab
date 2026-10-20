"""Reconstruct all real-engine returns and policy-gradient updates from evidence."""
import json
from pathlib import Path
import numpy as np

from cache_rl.learning import reward,update
from queueing_lab.provenance import write_json


def replay(directory):
    out=Path(directory)
    training=json.loads((out/'training.json').read_text())
    frozen=json.loads((out/'frozen-policy.json').read_text())
    jobs=json.loads((out/'jobs.json').read_text())
    reference_mode=training['reference_mode']
    references={}
    for job in jobs:
        if job['stage']=='training_reference':
            assert job['mode']==reference_mode
            references[job['family'],job['blocks'],job['seed']]=json.loads((out/f"job-{job['id']:03d}.json").read_text())
    weights=np.zeros((3,8));episodes=0;steps=0
    for iteration in range(6):
        trajectories=[];returns=[]
        batch=[e for e in training['episodes'] if e['iteration']==iteration]
        assert len(batch)==4
        for episode in batch:
            job=episode['job'];prefix=out/f"job-{job['id']:03d}"
            result=json.loads(prefix.with_suffix('.json').read_text())
            measured=reward(result,references[job['family'],job['blocks'],job['seed']])
            assert np.isclose(measured,episode['return_value'],atol=1e-12,rtol=1e-12)
            text=prefix.with_suffix('.stderr').read_text().split('CACHE_MEASUREMENT_START',1)[-1]
            trajectory=[json.loads(line[len('CACHE_ACTOR '):]) for line in text.splitlines() if line.startswith('CACHE_ACTOR ')]
            trajectories.append(trajectory);returns.append(measured)
            episodes+=1;steps+=len(trajectory)
        weights,statistics=update(weights,trajectories,returns)
        saved=json.loads((out/f'weights-{iteration:02d}.json').read_text())
        assert np.allclose(weights,saved['weights'],atol=1e-12,rtol=1e-12)
        assert np.isclose(statistics['gradient_norm'],saved['statistics']['gradient_norm'],atol=1e-12,rtol=1e-12)
    assert np.allclose(weights,frozen['weights'],atol=1e-12,rtol=1e-12)
    train_seeds={j['seed'] for j in jobs if j['stage'] in ('training','training_reference')}
    test_seeds={j['seed'] for j in jobs if j['stage']=='holdout'}
    assert not train_seeds.intersection(test_seeds)
    if test_seeds:assert max(j['id'] for j in jobs if j['stage']=='training')<min(j['id'] for j in jobs if j['stage']=='holdout')
    result={'episodes_replayed':episodes,'native_steps':steps,'updates_reproduced':6,
            'all_measured_returns_match':True,'all_saved_weights_match':True,
            'frozen_actor_matches':True,'train_holdout_seeds_disjoint':True}
    write_json(out/'replay-verification.json',result)
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('directory')
    print(json.dumps(replay(parser.parse_args().directory),indent=2))
