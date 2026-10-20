from pathlib import Path
import shutil
import subprocess
import hashlib
import zipfile
import io
import json
import tarfile
import os
import sys

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


def test_archived_source_audit_rejects_mutation(tmp_path):
    pytest.importorskip('numpy')
    from cache_rl.analyze import audit_archived_sources
    (tmp_path/'build').mkdir()
    digest=lambda value:hashlib.sha256(value).hexdigest()
    plan={'python_source':{'files':{'worker.py':digest(b'original')}},
          'frozen_native_source':{'manifest':{'files':{'scheduler.cpp':{'after':digest(b'native')}}}}}
    with zipfile.ZipFile(tmp_path/'source-snapshot.zip','w') as z:z.writestr('worker.py',b'original')
    with zipfile.ZipFile(tmp_path/'build/source-overlay.zip','w') as z:z.writestr('scheduler.cpp',b'native')
    assert audit_archived_sources(tmp_path,plan)=={'python':1,'native':1}
    with zipfile.ZipFile(tmp_path/'source-snapshot.zip','w') as z:z.writestr('worker.py',b'mutated')
    with pytest.raises(ValueError,match='source hash mismatch'):audit_archived_sources(tmp_path,plan)


@pytest.mark.parametrize('attack',['measured_library','model','candidate_wheel'])
def test_retained_build_audit_rejects_identity_mismatch(tmp_path,attack):
    pytest.importorskip('numpy')
    from cache_rl.analyze import audit_retained_build
    sha=lambda b:hashlib.sha256(b).hexdigest()
    def wheel(payload):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:z.writestr('onnxruntime_genai/libgenai.so',payload)
        return stream.getvalue()
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz',pax_headers={'comment':'pinned-source'}) as archive:
        info=tarfile.TarInfo('scheduler.cpp');info.size=1;archive.addfile(info,io.BytesIO(b'x'))
    files={'baseline-source.tar.gz':stream.getvalue(),'baseline.whl':wheel(b'baseline'),
           'candidate.whl':wheel(b'candidate'),
           'baseline-ready.json':json.dumps({'source':'pinned-source','model':{'model.onnx':'model-sha'}}).encode()}
    manifest={'files':{n:sha(b) for n,b in files.items()}}
    (tmp_path/'build').mkdir()
    path=tmp_path/'build/build-evidence.zip'
    with zipfile.ZipFile(path,'w') as z:
        for n,b in files.items():z.writestr(n,b)
        z.writestr('manifest.json',json.dumps(manifest))
    plan={'build_evidence':{'archive_sha256':sha(path.read_bytes()),'manifest':manifest},
          'frozen_native_source':{'source_base':'pinned-source','package':'/content/candidate-package','wheel_sha256':sha(files['candidate.whl'])}}
    libraries={'planner-baseline-package':{'libgenai.so':sha(b'baseline')},'candidate-package':{'libgenai.so':sha(b'candidate')}}
    models={'model.onnx':'model-sha'}
    assert 'retained source archive' in audit_retained_build(tmp_path,plan,libraries,models)['level']
    if attack=='measured_library':libraries['planner-baseline-package']['libgenai.so']='0'*64
    elif attack=='model':models['model.onnx']='changed'
    else:plan['frozen_native_source']['wheel_sha256']='0'*64
    with pytest.raises(ValueError):audit_retained_build(tmp_path,plan,libraries,models)


def test_worker_setup_failure_leaves_structured_artifact(tmp_path):
    pytest.importorskip('numpy')
    root=Path(__file__).resolve().parents[1]
    (tmp_path/'onnxruntime_genai.py').write_text("raise RuntimeError('injected setup failure')\n")
    output=tmp_path/'failed.json'
    process=subprocess.run([sys.executable,'-m','cache_rl.harness','--family','reuse','--blocks','32',
                            '--seed','123','--mode','baseline','--output',str(output)],
                           cwd=tmp_path,env=dict(os.environ,PYTHONPATH=str(tmp_path)+os.pathsep+str(root)),
                           capture_output=True,text=True,timeout=15)
    assert process.returncode!=0
    failure=json.loads(output.read_text())
    assert failure['status']=='failed' and failure['phase']=='before_complete_observation'
    assert 'injected setup failure' in failure['error']
    assert 'metrics' not in failure

