"""Audit every held-out cell, native identities and actual RL score traces."""
from collections import defaultdict
import hashlib
import io
import math
import random
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET
import zipfile
import tarfile

import numpy as np
from queueing_lab.provenance import file_hash,write_json
from queueing_lab.model import Config,RequestClass
from queueing_lab.validation import validate_observation
from queueing_lab.metrics import summarize
from queueing_lab.simulator import backlog_samples

METRICS=('restricted_mean_response_s','restricted_mean_ttft_s','observed_p99_gap_s')


def same_metrics(saved,recomputed):
    if isinstance(recomputed,dict):
        return isinstance(saved,dict) and set(saved)==set(recomputed) and all(same_metrics(saved[k],v) for k,v in recomputed.items())
    if isinstance(recomputed,float):
        return isinstance(saved,(float,int)) and math.isclose(saved,recomputed,rel_tol=1e-12,abs_tol=1e-12)
    return saved==recomputed


def audit_archived_sources(out,plan):
    """Verify executed source archives without substituting current files."""
    counts={}
    native=plan['frozen_native_source']['manifest']['files']
    for label,path,expected in (
        ('python',out/'source-snapshot.zip',plan['python_source']['files']),
        ('native',out/'build/source-overlay.zip',{k:v['after'] for k,v in native.items()}),
    ):
        with zipfile.ZipFile(path) as archive:
            names=archive.namelist()
            if len(names)!=len(set(names)) or set(names)!=set(expected):
                raise ValueError(f'{label} source archive membership mismatch')
            for name,digest in expected.items():
                if hashlib.sha256(archive.read(name)).hexdigest()!=digest:
                    raise ValueError(f'{label} source hash mismatch: {name}')
        counts[label]=len(expected)
    return counts


def audit_retained_build(out,plan,library_ids,model_files):
    record=plan.get('build_evidence')
    if record is None:return {'level':'recorded manifest consistency only; wheels/source archive absent'}
    path=out/'build/build-evidence.zip'
    if file_hash(path)!=record['archive_sha256']:raise ValueError('Build evidence archive hash mismatch')
    with zipfile.ZipFile(path) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        if manifest!=record['manifest']:raise ValueError('Build record differs from frozen plan')
        for name,digest in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=digest:raise ValueError('Build input/output hash mismatch: '+name)
        expected_source=plan['frozen_native_source']['source_base']
        baseline_ready=json.loads(archive.read('baseline-ready.json'))
        if baseline_ready['source']!=expected_source or baseline_ready['model']!=model_files:
            raise ValueError('Retained baseline source/model differs from measured identity')
        with tarfile.open(fileobj=io.BytesIO(archive.read('baseline-source.tar.gz'))) as source:
            if source.pax_headers.get('comment')!=expected_source:raise ValueError('Source archive revision mismatch')
        for name,package in [('baseline.whl','planner-baseline-package'),('candidate.whl',Path(plan['frozen_native_source']['package']).name)]:
            with zipfile.ZipFile(io.BytesIO(archive.read(name))) as wheel:
                for library,digest in library_ids[package].items():
                    matches=[n for n in wheel.namelist() if Path(n).name==library]
                    if len(matches)!=1 or hashlib.sha256(wheel.read(matches[0])).hexdigest()!=digest:
                        raise ValueError('Measured library differs from retained wheel: '+library)
        if manifest['files']['candidate.whl']!=plan['frozen_native_source']['wheel_sha256']:
            raise ValueError('Candidate wheel differs from native build record')
    return {'level':'retained source archive, build log and wheels; measured library hashes verified',
            'source_revision':expected_source,'archive_sha256':record['archive_sha256'],
            'limit':'Build record consistency, not an independent hermetic rebuild or attestation'}


def analyze(directory,require_complete=True):
    out=Path(directory)
    plan=json.loads((out/'plan.json').read_text())
    source_counts=audit_archived_sources(out,plan)
    jobs=json.loads((out/'jobs.json').read_text())
    heuristic='coalesce' if any(j['mode']=='coalesce' for j in jobs) else 'cache'
    candidate_package=Path(plan['frozen_native_source']['package']).name
    if require_complete:
        assert json.loads((out/'complete.json').read_text())['jobs']==len(jobs)==124
    rows=[];library_ids={};model_identity=None;all_complete_outputs=0;output_errors=[]
    for job in jobs:
        p=out/f"job-{job['id']:03d}.json"
        if not p.exists():
            if require_complete:raise ValueError(f'Missing result {p.name}')
            continue
        r=json.loads(p.read_text());assert r['job']==job
        expected_config=Config(classes=(RequestClass('long',1537,32,64),RequestClass('short',769,32,64)),
                               rows=16,blocks=job['blocks'],block_size=256)
        # Legacy cache snapshots hashed input token arrays that were then removed.
        # Their digests can be compared across arms but not reconstructed here.
        trace=validate_observation(r,expected_config,plan['horizon_s'],'native',plan.get('canonical_trace_hash',False))
        rng=random.Random(job['seed'])
        expected_trace=[{'id':i,'class_id':0 if i%3 else 1,
                         'arrival':(0 if i<32 else .12 if i<48 else .24)+rng.uniform(0,.004)} for i in range(64)]
        expected_trace.sort(key=lambda q:(q['arrival'],q['id']))
        if trace!=expected_trace:raise ValueError('Offered arrivals differ from frozen workload')
        payload=hashlib.sha256(json.dumps([(q['id'],q['prompt_sha256'],q['max_new']) for q in r['requests']],sort_keys=True).encode()).hexdigest()
        if payload!=r['payload_sha256']:raise ValueError('Payload digest differs from retained request metadata')
        recomputed=summarize(r['requests'],plan['horizon_s'],backlog_samples(r['requests'],plan['horizon_s'],.1))
        if not same_metrics(r['metrics'],recomputed):raise ValueError('Saved metrics differ from raw offered/event accounting')
        if r['family']!=job['family'] or r['blocks']!=job['blocks'] or r['seed']!=job['seed'] or r['mode']!=job['mode']:
            raise ValueError('Workload semantics differ from frozen job')
        assert len(r['requests'])==r['metrics']['offered']==64
        baseline=job['mode'] in ('baseline','baseline_aa') or (job['mode']=='shortest' and plan.get('fixed_shortest_native_builtin',False))
        provenance=r['provenance'];package='planner-baseline-package' if baseline else candidate_package
        if model_identity is None:model_identity=provenance['model_files']
        elif provenance['model_files']!=model_identity:raise ValueError('Model identity changed between jobs')
        db=provenance['engine_config']['engine']['dynamic_batching']
        expected_db={'block_size':256,'num_blocks':job['blocks'],'max_batch_size':16,
                     'max_scheduled_tokens':2048,'prefix_caching':True}
        if any(db.get(k)!=v for k,v in expected_db.items()):raise ValueError('Engine resources differ from experiment plan')
        expected_shortest=job['mode']=='shortest' and plan.get('fixed_shortest_native_builtin',False)
        if db.get('cheapest_prefill_first',False)!=expected_shortest:raise ValueError('Unexpected native shortest-prefill setting')
        assert f'/{package}/' in provenance['module']
        assert provenance['loaded_genai_libraries']
        assert all(f'/{package}/' in p for p in provenance['loaded_genai_libraries'])
        ident=provenance['package_libraries']
        if package in library_ids:assert ident==library_ids[package]
        else:library_ids[package]=ident
        for request in r['requests']:
            assert len(request['tokens'])==len(request['token_times'])
            if request['finish'] is not None:assert len(request['tokens'])==32
        rows.append(r)
    lookup={(r['job']['stage'],r['family'],r['blocks'],r['seed'],r['mode']):r for r in rows}
    pairs=[]
    for r in rows:
        if r['job']['stage'] not in ('cache_screen','holdout','identity_control'):continue
        stage=r['job']['stage'];mode=r['mode']
        if mode=='baseline':continue
        base_stage='cache_screen' if stage=='identity_control' else stage
        base=lookup[base_stage,r['family'],r['blocks'],r['seed'],'baseline']
        assert r['trace_sha256']==base['trace_sha256'] and r['payload_sha256']==base['payload_sha256']
        assert r['provenance']['model_files']==base['provenance']['model_files']
        def normalized_engine_config(value):
            value=json.loads(json.dumps(value))
            value['engine']['dynamic_batching'].pop('cheapest_prefill_first',None)
            return value
        assert normalized_engine_config(r['provenance']['engine_config'])==normalized_engine_config(base['provenance']['engine_config'])
        if plan.get('fixed_shortest_native_builtin') and mode=='shortest':
            assert r['provenance']['engine_config']['engine']['dynamic_batching']['cheapest_prefill_first'] is True
        bmap={q['id']:q for q in base['requests']}
        max_ttft=max_completion=0
        for request in r['requests']:
            b=bmap[request['id']]
            assert (request['arrival'],request['prompt_sha256'])==(b['arrival'],b['prompt_sha256'])
            common=min(len(request['tokens']),len(b['tokens']))
            if request['tokens'][:common]!=b['tokens'][:common]:output_errors.append(dict(job=r['job'],id=request['id']))
            if request['finish'] is not None and b['finish'] is not None:
                all_complete_outputs+=1
                max_completion=max(max_completion,request['finish']-b['finish'])
            if request['token_times'] and b['token_times']:
                max_ttft=max(max_ttft,request['token_times'][0]-b['token_times'][0])
        comparisons={}
        references=('baseline','shortest') if mode==heuristic else ('baseline','shortest',heuristic) if mode=='rl' else ('baseline',)
        for control in references:
            b=lookup.get((base_stage,r['family'],r['blocks'],r['seed'],control))
            if b is None:continue
            compare={}
            for metric in METRICS+('burst_throughput_s','host_cpu_s'):
                x=b.get(metric) if metric in ('burst_throughput_s','host_cpu_s') else b['metrics'][metric]
                y=r.get(metric) if metric in ('burst_throughput_s','host_cpu_s') else r['metrics'][metric]
                compare[metric]=dict(baseline=x,candidate=y,pct=100*(y/x-1) if x not in (None,0) and y is not None else None)
            comparisons[control]=compare
        pairs.append(dict(job=r['job'],against=comparisons,max_individual_ttft_later_s=max_ttft,
                          max_individual_completion_later_s=max_completion))

    # Confirm the logged actor probabilities came from the frozen pre-update
    # weights, not a label predictor or post-hoc action annotation.
    native_steps=0;action_counts=[0,0,0]
    for r in rows:
        if r['mode']!='rl_train':continue
        training=json.loads((out/'training.json').read_text())
        episode=next(e for e in training['episodes'] if e['job']['id']==r['job']['id'])
        iteration=episode['iteration']
        weights=np.zeros((3,8)) if iteration==0 else np.asarray(json.loads((out/f'weights-{iteration-1:02d}.json').read_text())['weights'])
        text=(out/f"job-{r['job']['id']:03d}.stderr").read_text().split('CACHE_MEASUREMENT_START',1)[-1]
        for line in text.splitlines():
            if not line.startswith('CACHE_ACTOR '):continue
            step=json.loads(line[len('CACHE_ACTOR '):]);state=np.asarray(step['state']);mask=np.asarray(step['mask'],dtype=bool)
            logits=np.where(mask,weights@state,-np.inf);prob=np.exp(logits-np.max(logits));prob/=prob.sum()
            assert np.allclose(prob,step['probability'],atol=2e-12,rtol=2e-12)
            assert mask[step['action']] and prob[step['action']]>0
            native_steps+=1;action_counts[step['action']]+=1
    flags=[]
    for mode in (heuristic,'rl'):
        cases=[p for p in pairs if p['job']['stage']=='holdout' and p['job']['mode']==mode]
        for p in cases:
            for control,comparison in p['against'].items():
                bad=[m for m in METRICS if comparison[m]['pct'] is None or comparison[m]['pct']>2]
                if bad:flags.append(dict(job=p['job'],control=control,metrics=bad))
    tests={}
    for name in ('focused','full'):
        path=out/'build'/f'{name}-tests.xml'
        if path.exists():
            root=ET.parse(path).getroot();tests[name]={k:root.get(k) for k in ('tests','failures','disabled','errors')}
    build_audit=audit_retained_build(out,plan,library_ids,model_identity) if require_complete else {'level':'partial checkpoint; build bundle checked at completion'}
    summary={'jobs':len(rows),'build_provenance':build_audit,'archived_sources_verified':source_counts,'heuristic':heuristic,'builtin_shortest_control':plan.get('fixed_shortest_native_builtin',False),'offered':sum(r['metrics']['offered'] for r in rows),
             'completed':sum(r['metrics']['completed'] for r in rows),'failed_jobs':[r['job'] for r in rows if r['status']!='observed'],
             'output_errors':output_errors,'complete_paired_outputs':all_complete_outputs,
             'native_rl_decisions_verified':native_steps,'training_action_counts':action_counts,
             'heldout_cost_flags':flags,'library_ids':library_ids,'engine_tests':tests,'pairs':pairs,
             'runs':[dict(job=r['job'],metrics=r['metrics'],burst_throughput_s=r['burst_throughput_s'],host_cpu_s=r['host_cpu_s'],
                          cached_prompt_tokens=sum(q['cached_prompt_tokens'] or 0 for q in r['requests']),
                          raw_sha256=file_hash(out/f"job-{r['job']['id']:03d}.json")) for r in rows]}
    write_json(out/'analysis.json',summary)
    render(out,summary)
    return summary


def render(out,summary):
    groups=defaultdict(list)
    for row in summary['runs']:
        if row['job']['stage']=='holdout':groups[row['job']['family'],row['job']['blocks'],row['job']['mode']].append(row)
    lines=['# Native cache-aware scheduling and actual-engine RL','',
        'All policies operate inside continuous batching. No external cohort gate or prefill-budget cap is used.',
        'These are finite burst workloads; burst throughput is 64/final completion time, not a sustainable arrival-rate result. The plan has two held-out seeds per cell.',
        summary['build_provenance']['level'],
        f"Collected training jobs: {sum(r['job']['stage']=='training' for r in summary['runs'])}; collected held-out jobs: {sum(r['job']['stage']=='holdout' for r in summary['runs'])}.",
        '', '| Family | KV blocks | Policy | Burst req/s | Restricted TTFT, ms | Restricted response, ms | Observed p99 gap, ms | Cached prompt tokens | Host CPU, s |',
        '|---|---:|---|---:|---:|---:|---:|---:|---:|']
    for (family,blocks,mode),rows in sorted(groups.items()):
        avg=lambda key:statistics.mean(r[key] for r in rows)
        metric=lambda key:statistics.mean(r['metrics'][key] for r in rows)
        speed=[r['burst_throughput_s'] for r in rows]
        throughput=f'{statistics.mean(speed):.2f}' if all(x is not None for x in speed) else 'incomplete'
        lines.append(f"| {family} | {blocks} | {mode} | {throughput} | {metric('restricted_mean_ttft_s')*1000:.2f} | {metric('restricted_mean_response_s')*1000:.2f} | {metric('observed_p99_gap_s')*1000:.2f} | {avg('cached_prompt_tokens'):.0f} | {avg('host_cpu_s'):.3f} |")
    lines+=['',f"Actual native RL decisions whose probabilities match the pre-update actor: {summary['native_rl_decisions_verified']}. Action counts: {summary['training_action_counts']}.",
        f"Held-out per-trace/control cost flags above 2%: {len(summary['heldout_cost_flags'])}. Every flag is retained in analysis.json. A partial checkpoint without held-out jobs has no performance verdict. These flags are point estimates, not confidence-bounded non-regression tests.",
        f"Offered/completed across all jobs: {summary['offered']}/{summary['completed']}. Failed jobs: {len(summary['failed_jobs'])}. Paired complete output comparisons: {summary['complete_paired_outputs']}; mismatches: {len(summary['output_errors'])}.",
        '', 'The training reference is selected from the fixed development screen only. The plan uses 24 actual GPU episodes and six REINFORCE updates; final weights freeze before held-out evaluation. Collected checkpoints, returns and trajectories are retained.',
        'The 64-opportunity age override gives priority; it does not guarantee wall-clock completion. Greedy ranking, prefix matching and host overhead have costs. Engine allocator invariants remain authoritative. See the frozen plan for the pre-run protocol.']
    for mode in (summary['heuristic'],'rl'):
        cases=[p for p in summary['pairs'] if p['job']['stage']=='holdout' and p['job']['mode']==mode]
        if cases:
            ttft=max(0,max(p['max_individual_ttft_later_s'] for p in cases))
            completion=max(0,max(p['max_individual_completion_later_s'] for p in cases))
            lines.append(f"Largest matched individual cost for {mode} versus baseline: TTFT {ttft*1000:.2f} ms later; completion {completion*1000:.2f} ms later. Better means do not remove these costs.")
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--partial',action='store_true')
    args=parser.parse_args();result=analyze(args.directory,not args.partial)
    print(json.dumps({k:result[k] for k in ('jobs','offered','completed','native_rl_decisions_verified','training_action_counts')},indent=2))
