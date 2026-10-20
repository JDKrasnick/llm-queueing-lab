"""Audit every held-out cell, native identities and actual RL score traces."""
from collections import defaultdict
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
from queueing_lab.provenance import file_hash,write_json

METRICS=('restricted_mean_response_s','restricted_mean_ttft_s','observed_p99_gap_s')


def analyze(directory,require_complete=True):
    out=Path(directory)
    plan=json.loads((out/'plan.json').read_text())
    jobs=json.loads((out/'jobs.json').read_text())
    heuristic='coalesce' if any(j['mode']=='coalesce' for j in jobs) else 'cache'
    candidate_package=Path(plan['frozen_native_source']['package']).name
    if require_complete:
        assert json.loads((out/'complete.json').read_text())['jobs']==len(jobs)==124
    rows=[];library_ids={};all_complete_outputs=0;output_errors=[]
    for job in jobs:
        p=out/f"job-{job['id']:03d}.json"
        if not p.exists():
            if require_complete:raise ValueError(f'Missing result {p.name}')
            continue
        r=json.loads(p.read_text());assert r['job']==job
        assert len(r['requests'])==r['metrics']['offered']==64
        baseline=job['mode'] in ('baseline','baseline_aa') or (job['mode']=='shortest' and plan.get('fixed_shortest_native_builtin',False))
        provenance=r['provenance'];package='planner-baseline-package' if baseline else candidate_package
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
    summary={'jobs':len(rows),'heuristic':heuristic,'builtin_shortest_control':plan.get('fixed_shortest_native_builtin',False),'offered':sum(r['metrics']['offered'] for r in rows),
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
        'These are finite burst workloads; burst throughput is64/final completion time, not a sustainable arrival-rate result. Two held-out seeds per cell.',
        '', '| Family | KV blocks | Policy | Burst req/s | Restricted TTFT, ms | Restricted response, ms | Observed p99 gap, ms | Cached prompt tokens |',
        '|---|---:|---|---:|---:|---:|---:|---:|']
    for (family,blocks,mode),rows in sorted(groups.items()):
        avg=lambda key:statistics.mean(r[key] for r in rows)
        metric=lambda key:statistics.mean(r['metrics'][key] for r in rows)
        speed=[r['burst_throughput_s'] for r in rows]
        throughput=f'{statistics.mean(speed):.2f}' if all(x is not None for x in speed) else 'incomplete'
        lines.append(f"| {family} | {blocks} | {mode} | {throughput} | {metric('restricted_mean_ttft_s')*1000:.2f} | {metric('restricted_mean_response_s')*1000:.2f} | {metric('observed_p99_gap_s')*1000:.2f} | {avg('cached_prompt_tokens'):.0f} |")
    lines+=['',f"Actual native RL decisions whose probabilities match the pre-update actor: {summary['native_rl_decisions_verified']}. Action counts: {summary['training_action_counts']}.",
        f"Held-out per-trace/control cost flags above2%: {len(summary['heldout_cost_flags'])}. Every flag is retained in analysis.json; no universal latency dominance or non-regression is established by a small screen.",
        f"Offered/completed across all jobs: {summary['offered']}/{summary['completed']}. Failed jobs: {len(summary['failed_jobs'])}. Paired complete output comparisons: {summary['complete_paired_outputs']}; mismatches: {len(summary['output_errors'])}.",
        '', 'The training reference is selected from the fixed development screen only.24 actual GPU episodes use six REINFORCE updates; two fresh seeds per family/capacity are held out. Final weights and every checkpoint/return/trajectory are retained.',
        'The64-opportunity age override is a bounded priority override, not a wall-clock completion guarantee. Greedy ranking, prefix matching and logging/host overhead have costs. Engine allocator invariants remain authoritative. See PLAN.md for the pre-run protocol.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--partial',action='store_true')
    args=parser.parse_args();result=analyze(args.directory,not args.partial)
    print(json.dumps({k:result[k] for k in ('jobs','offered','completed','native_rl_decisions_verified','training_action_counts')},indent=2))
