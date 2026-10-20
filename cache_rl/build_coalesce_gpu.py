"""Incrementally build the research overlay in the authorized Colab runtime."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sysconfig
import zipfile


def main():
    stage=Path('/content/cache-coalesce-build');stage.mkdir(exist_ok=False)
    bundle=Path(__file__).resolve().parents[1]
    source=Path('/content/planner-source')
    manifest=json.loads((bundle/'native/coalesce-source-manifest.json').read_text())
    with zipfile.ZipFile(bundle/'native/coalesce-source-overlay.zip') as overlay:
        for name,item in manifest['files'].items():
            path=source/name
            if path.exists():
                actual=hashlib.sha256(path.read_bytes()).hexdigest()
                if actual not in item['allowed_before']+[item['after']]:
                    raise RuntimeError(f'Unexpected source version {name}: {actual}')
            elif item['allowed_before'] and name!='src/engine/research_cache_policy.h':
                raise RuntimeError(f'Missing source {name}')
            path.write_bytes(overlay.read(name))
            if hashlib.sha256(path.read_bytes()).hexdigest()!=item['after']:raise RuntimeError(name)
    (stage/'source-manifest.json').write_text(json.dumps(manifest,indent=2))
    env=dict(os.environ,**json.loads(Path('/content/planner-validation/environment.json').read_text()))
    for key in list(env):
        if key.startswith('GENAI_RESEARCH_'):env.pop(key)
    build=source/'build/Linux/Release'
    for target in ['engine_unit_tests','python','PyPackageBuild']:
        subprocess.run(['cmake','--build',str(build),'--target',target,'--parallel','4'],env=env,check=True)
    ep=Path(sysconfig.get_path('platlib'))/'onnxruntime_ep_cuda'
    for label,pattern in [('focused','DecodeFirstSchedulerPolicyTest.*:SchedulerContractTest.*:DynamicBatchingConfigTest.*'),('full','*')]:
        with (stage/f'{label}-tests.log').open('w') as f:
            subprocess.run([str(build/'engine_unit_tests'),'--ep_dir',str(ep),'--gtest_filter='+pattern,
                '--gtest_output=xml:'+str(stage/f'{label}-tests.xml')],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    wheel=next((build/'wheel').glob('*.whl'))
    package=Path('/content/cache-coalesce-package');package.mkdir(exist_ok=False)
    with zipfile.ZipFile(wheel) as z:z.extractall(package)
    shutil.copy2(wheel,stage/wheel.name)
    (stage/'ready.json').write_text(json.dumps({'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),
        'manifest':manifest,'package':str(package),'source_base':manifest['base']},indent=2))
    print('CACHE_RL_BUILD_COMPLETE',flush=True)


if __name__=='__main__':main()
