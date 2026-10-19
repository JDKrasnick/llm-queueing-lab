"""Run only in the authorized Colab GPU runtime, against the frozen base package.

Every arm is a fresh process. Two seeds, three load levels, three policies,
plus a second native run for each trace: 24 measured jobs, all retained.
"""

import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from queueing_lab.model import Catalog, Config, RequestClass
from queueing_lab.provenance import manifest, write_json


def main():
    output=Path(os.environ.get('QUEUEING_GPU_OUTPUT','/content/llm-queueing-lab-gpu-v1'))
    output.mkdir(exist_ok=False)
    config=Config(classes=(RequestClass('prefill',769,16,32),RequestClass('decode',65,96,128)),
                  rows=4,blocks=16,block_size=256)
    write_json(output/'config.json',config.as_dict())
    environment=dict(os.environ)
    # Reuse the CUDA/cuDNN library paths of the already validated GPU build.
    environment.update(json.loads(Path('/content/planner-validation/environment.json').read_text()))
    environment['PYTHONPATH']='/content/planner-baseline-package:'+str(ROOT)
    environment['MPLBACKEND']='Agg'
    common=[sys.executable,'-m','queueing_lab']
    model='/content/planner-qwen-paged'
    plan={'schema':1,'seeds':[20261101,20261102],'loads':[.5,.85,1.05], 'horizon_s':12,
          'arms':['native','native_aa','fcfs','pressure'],
          'calibration_reps':2,'model':model,'package':'/content/planner-baseline-package',
          'purpose':'Gated model transfer and native continuous-admission control; not always-on cap validation',
          'source':manifest(ROOT),'config':config.as_dict(),
          'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,uuid,driver_version','--format=csv'],text=True)}
    write_json(output/'plan.json',plan)

    def run(command,log):
        with log.open('w') as f:
            result=subprocess.run(command,env=environment,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=240)
        if result.returncode:
            print(log.read_text()[-6000:],flush=True)
            raise RuntimeError(f'Process failed {result.returncode}: {log.name}')

    run(common+['calibrate','--config',str(output/'config.json'),'--model',model,
                '--output',str(output/'calibration.json'),'--reps','2'],output/'calibration.log')
    table=json.loads((output/'calibration.json').read_text())
    catalog=Catalog(config,{tuple(e['action']):e['mean_s'] for e in table['entries']})
    capacity=catalog.capacity((.5,.5))
    write_json(output/'empirical-gated-capacity.json',dict(capacity,monotone=catalog.monotone(),
               warning='Empirical gated service-rate hull, not native Engine capacity or a stability proof'))
    jobs=[]
    rng=random.Random(2026101901)
    for seed in plan['seeds']:
        for load in plan['loads']:
            arms=plan['arms'].copy(); rng.shuffle(arms)
            for arm in arms:
                jobs.append(dict(id=len(jobs),seed=seed,load=load,rate=capacity['requests_s']*load,arm=arm))
    write_json(output/'jobs.json',jobs)
    for job in jobs:
        name=f"job-{job['id']:03d}"
        print('START',json.dumps(job),flush=True)
        run(common+['hardware','--model',model,'--table',str(output/'calibration.json'),
                    '--output',str(output/(name+'.json')),'--policy','native' if job['arm']=='native_aa' else job['arm'],
                    '--rate',str(job['rate']),'--horizon','12','--seed',str(job['seed'])],output/(name+'.log'))
        result=json.loads((output/(name+'.json')).read_text())
        result['job']=job
        write_json(output/(name+'.json'),result)
        print('END',job['id'],result['status'],result['metrics'],flush=True)
    write_json(output/'complete.json',dict(jobs=len(jobs),finished_at=time.time()))
    archive=Path(str(output)+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in output.rglob('*'):
            if p.is_file(): z.write(p,p.relative_to(output))
        for p in ROOT.rglob('*.py'):
            if '__pycache__' not in p.parts: z.write(p,'source/'+str(p.relative_to(ROOT)))
    print('COMPLETE',archive,hashlib.sha256(archive.read_bytes()).hexdigest(),flush=True)


if __name__=='__main__': main()
