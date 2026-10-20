"""Fixed cache screen first, actual-Engine policy-gradient training second.

Frozen test seeds never enter fitting. Every job runs in a fresh process.
This burst experiment reports makespan throughput as well as fixed-window
counts; it does not claim a sustainable arrival-rate/stability measurement.
"""
from pathlib import Path
import atexit
import hashlib
import json
import os
import random
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from cache_rl.learning import reward,update
from queueing_lab.provenance import manifest,snapshot,write_json

FAMILIES=('reuse','churn','phase','no_prefix')


def main():
    out=Path('/content/cache-coalesce-results-v1');out.mkdir(exist_ok=False)
    build=Path('/content/cache-coalesce-build')
    ready=json.loads((build/'ready.json').read_text())
    write_json(out/'plan.json',{'stage_order':['fixed_cache_screen','reinforce_training','frozen_holdout'],
        'fixed_shortest_native_builtin':True,'cold_prefix_key_tokens':512,'canonical_trace_hash':True,
        'build_evidence':json.loads((build/'build-evidence.json').read_text()),
        'recovery_note':'Repeat after original archive was lost with expired Colab runtime. Validation fixes applied before any repeat measurements; no policy or seed retuning.',
        'families':FAMILIES,'blocks':[32,128],'horizon_s':6,'requests':64,
        'screen_seed':20262301,'training_seeds':[20262401,20262402],
        'holdout_seeds':[20262501,20262502],'training_updates':6,'episodes_per_update':4,
        'actions':['FIFO','shortest uncached prefill','exact-prefix admission coalescing'],
        'frozen_native_source':ready,'python_source':manifest(ROOT),
        'qualification':'Complete/correct outputs; >=5% gain in TTFT or burst throughput, no >2% response/TTFT/p99-gap loss against both baseline and shortest in every held-out cell; costs reported even if gate fails.'})
    snapshot(ROOT,out/'source-snapshot.zip',json.loads((out/'plan.json').read_text())['python_source'])
    env=dict(os.environ,**json.loads(Path('/content/planner-validation/environment.json').read_text()))
    for key in list(env):
        if key.startswith('GENAI_RESEARCH_'):env.pop(key)
    jobs=[]

    def job(stage,family,blocks,seed,mode,weights=None):
        number=len(jobs);name=f'job-{number:03d}'
        specification=dict(id=number,stage=stage,family=family,blocks=blocks,seed=seed,mode=mode)
        jobs.append(specification);write_json(out/'jobs.json',jobs)
        candidate=mode not in ('baseline','baseline_aa','shortest')
        job_env=dict(env,PYTHONPATH=('/content/cache-coalesce-package' if candidate else '/content/planner-baseline-package')+':'+str(ROOT))
        if mode not in ('baseline','baseline_aa','off'):
            job_env['GENAI_RESEARCH_CACHE_POLICY']=mode
        if mode=='rl_train':
            job_env['GENAI_RESEARCH_CACHE_TRACE']='1'
        if weights is not None:
            job_env['GENAI_RESEARCH_CACHE_WEIGHTS']=','.join(format(float(x),'.17g') for x in np.asarray(weights).ravel())
        job_env['GENAI_RESEARCH_CACHE_SEED']=str(800000+number)
        job_env['CACHE_USE_BUILTIN_SHORTEST']='1'
        print('START',json.dumps(specification),flush=True)
        with (out/(name+'.log')).open('w') as stdout,(out/(name+'.stderr')).open('w') as stderr:
            try:
                process=subprocess.run([sys.executable,'-m','cache_rl.harness','--family',family,'--blocks',str(blocks),
                    '--seed',str(seed),'--mode',mode,'--output',str(out/(name+'.json'))],env=job_env,cwd=ROOT,
                    stdout=stdout,stderr=stderr,timeout=150)
            except subprocess.TimeoutExpired:
                write_json(out/(name+'-failure.json'),dict(job=specification,status='failed',phase='worker_watchdog',timeout_s=150))
                raise
        if process.returncode:
            write_json(out/(name+'-failure.json'),dict(job=specification,status='failed',phase='worker',returncode=process.returncode))
            raise RuntimeError((out/(name+'.stderr')).read_text()[-1500:])
        result=json.loads((out/(name+'.json')).read_text());result['job']=specification
        result['burst_throughput_s']=64/max(r['finish'] for r in result['requests']) if result['metrics']['completed']==64 else None
        text=(out/(name+'.stderr')).read_text().split('CACHE_MEASUREMENT_START',1)
        trajectory=[json.loads(line[len('CACHE_ACTOR '):]) for line in text[-1].splitlines() if line.startswith('CACHE_ACTOR ')]
        result['actor_decisions_logged']=len(trajectory)
        write_json(out/(name+'.json'),result)
        print('END',number,result['status'],result['metrics']['completed'],'TTFT',result['metrics']['restricted_mean_ttft_s'],flush=True)
        return result,trajectory

    def archive(label):
        path=Path('/content/cache-coalesce-'+label+'.zip')
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
            for p in out.rglob('*'):
                if p.is_file():z.write(p,p.relative_to(out))
            for name in ('ready.json','full-tests.xml','focused-tests.xml','full-tests.log','focused-tests.log'):
                z.write(build/name,'build/'+name)
            z.write(ROOT/'native/coalesce-source-overlay.zip','build/source-overlay.zip')
            if label=='complete':z.write('/content/cache-build-evidence.zip','build/build-evidence.zip')
        checksum=hashlib.sha256(path.read_bytes()).hexdigest()
        write_json(Path(str(path)+'.ready.json'),{'bytes':path.stat().st_size,'sha256':checksum})
        print('CHECKPOINT',label,path.stat().st_size,checksum,flush=True)

    atexit.register(lambda:archive('incomplete') if not (out/'complete.json').exists() else None)

    rng=random.Random(202610193)
    screen=[]
    for family in FAMILIES:
        for blocks in (32,128):
            modes=['baseline','shortest','coalesce'];rng.shuffle(modes)
            for mode in modes:screen.append(job('cache_screen',family,blocks,20262301,mode)[0])
    for family in ('reuse','no_prefix'):
        for mode in ('off','baseline_aa'):job('identity_control',family,32,20262301,mode)
    write_json(out/'cache-screen-complete.json',{'jobs':len(jobs)})
    archive('cache-screen')
    print('CACHE_SCREEN_COMPLETE; starting actual native-engine REINFORCE',flush=True)

    # Freeze the strongest fixed control from development screen only.
    scores={}
    for mode in ('baseline','shortest','coalesce'):
        rows=[r for r in screen if r['mode']==mode]
        scores[mode]=float(np.mean([r['metrics']['restricted_mean_response_s']+r['metrics']['restricted_mean_ttft_s'] for r in rows]))
    reference_mode=min(scores,key=scores.get)
    references={}
    training_traces=[(FAMILIES[i],blocks,20262401+i%2) for i in range(4) for blocks in (32,128)]
    for family,blocks,seed in training_traces:
        references[family,blocks,seed]=job('training_reference',family,blocks,seed,reference_mode)[0]
    weights=np.zeros((3,8));training=[]
    for iteration in range(6):
        trajectories=[];returns=[]
        selected=rng.sample(training_traces,4)
        for family,blocks,seed in selected:
            result,trajectory=job('training',family,blocks,seed,'rl_train',weights)
            value=reward(result,references[family,blocks,seed])
            trajectories.append(trajectory);returns.append(value)
            training.append(dict(iteration=iteration,job=result['job'],return_value=value,decisions=len(trajectory)))
        weights,statistics=update(weights,trajectories,returns)
        write_json(out/f'weights-{iteration:02d}.json',{'weights':weights.tolist(),'statistics':statistics})
        write_json(out/'training.json',{'reference_mode':reference_mode,'reference_scores':scores,'episodes':training})
        print('RL_UPDATE',iteration,statistics,flush=True)
    write_json(out/'frozen-policy.json',{'weights':weights.tolist(),'updates':6,'training_episodes':24,
               'algorithm':'episodic REINFORCE with leave-one-out baseline, score gradient, norm clipping',
               'reference_mode':reference_mode,'training_only_seeds':[20262401,20262402]})
    archive('trained')
    for seed in (20262501,20262502):
        for family in FAMILIES:
            for blocks in (32,128):
                modes=['baseline','shortest','coalesce','rl'];rng.shuffle(modes)
                for mode in modes:job('holdout',family,blocks,seed,mode,weights if mode=='rl' else None)
    write_json(out/'complete.json',{'jobs':len(jobs),'training_episodes':24,'finished_at':time.time()})
    archive('complete')


if __name__=='__main__':main()
