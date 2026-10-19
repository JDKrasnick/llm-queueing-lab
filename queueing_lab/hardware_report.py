"""Validate identities and matched traces before reporting any hardware result."""

from collections import defaultdict
import copy
import hashlib
import json
from pathlib import Path
import statistics

from .metrics import summarize
from .model import Catalog, Config
from .provenance import file_hash, write_json
from .simulator import backlog_samples
from .workload import trace_hash


def require(condition, message):
    if not condition:
        raise ValueError(message)


def analyze(directory):
    out=Path(directory)
    plan=json.loads((out/'plan.json').read_text())
    jobs=json.loads((out/'jobs.json').read_text())
    complete=json.loads((out/'complete.json').read_text())
    require(complete['jobs']==len(jobs)==24,"Incomplete 24-job experiment")
    calibration=json.loads((out/'calibration.json').read_text())
    build_path=out/'baseline-build-provenance.json'
    baseline_source=None
    if build_path.exists():
        build=json.loads(build_path.read_text())
        require(all(build['libraries'].get(name)==digest for name,digest in
                    calibration['provenance']['package_libraries'].items()),"Measured libraries differ from built baseline wheel")
        baseline_source=build['baseline_ready']['source']
    config=Config.from_dict(calibration['config'])
    catalog=Catalog(config,{tuple(e['action']):e['mean_s'] for e in calibration['entries']})
    require(calibration['complete'] and config==Config.from_dict(plan['config']),"Calibration/config mismatch")
    rows=[]
    identities=('package_libraries','model_files','engine_config','prompt_sha256','provider')
    for job in jobs:
        path=out/f"job-{job['id']:03d}.json"
        result=json.loads(path.read_text())
        require(result['backend']=='onnxruntime-genai-engine',"Not actual-engine evidence")
        require(result['calibration_sha256']==file_hash(out/'calibration.json'),"Calibration file hash mismatch")
        require(result['job']==job,"Job plan mismatch")
        for key in identities:
            require(result['provenance'][key]==calibration['provenance'][key],f"Runtime identity mismatch: {key}")
        paths=result['provenance']['loaded_genai_libraries']
        require(paths and all('/planner-baseline-package/' in p for p in paths),"Loaded GenAI library outside baseline package")
        trace=[{k:r[k] for k in ('id','arrival','class_id')} for r in result['requests']]
        require(trace_hash(trace)==result['trace_sha256'],"Offered trace hash mismatch")
        for request in result['requests']:
            require(len(request['tokens'])==len(request['token_times']),"Token/time count mismatch")
            require(hashlib.sha256(json.dumps(request['tokens']).encode()).hexdigest()==request['output_sha256'],"Output token hash mismatch")
            require(all(request['arrival']<=t<=result['horizon_s'] for t in request['token_times']),"Publication outside observation window")
            if request['finish'] is not None:
                require(len(request['tokens'])==config.classes[request['class_id']].output_tokens,"Completed output length mismatch")
        # Old GPU snapshot lacks restricted TTFT; derive it transparently from
        # the immutable complete event log, retaining the original raw files.
        result['derived_metrics']=summarize(result['requests'],result['horizon_s'],
            backlog_samples(result['requests'],result['horizon_s'],.1))
        result['raw_sha256']=file_hash(path)
        rows.append(result)
    pairs=[];matched=0;mismatches=[];prefix_mismatches=[]
    lookup={(r['job']['seed'],r['job']['load'],r['job']['arm']):r for r in rows}
    for seed in plan['seeds']:
        for load in plan['loads']:
            base=lookup[seed,load,'native']
            for arm in ('native_aa','fcfs','pressure'):
                candidate=lookup[seed,load,arm]
                require(base['trace_sha256']==candidate['trace_sha256'],"Paired offered traces differ")
                for b,c in zip(base['requests'],candidate['requests'],strict=True):
                    require((b['id'],b['arrival'],b['class_id'])==(c['id'],c['arrival'],c['class_id']),"Paired request identities differ")
                    common=min(len(b['tokens']),len(c['tokens']))
                    if b['tokens'][:common]!=c['tokens'][:common]:
                        prefix_mismatches.append(dict(seed=seed,load=load,arm=arm,id=b['id']))
                    if b['finish'] is not None and c['finish'] is not None:
                        matched+=1
                        if b['tokens']!=c['tokens']:
                            mismatches.append(dict(seed=seed,load=load,arm=arm,id=b['id']))
                metrics={}
                for key in ('completion_rate_s','restricted_mean_response_s','restricted_mean_ttft_s','observed_p99_gap_s','unfinished'):
                    b=base['derived_metrics'][key];c=candidate['derived_metrics'][key]
                    metrics[key]=dict(baseline=b,candidate=c,relative_pct=100*(c/b-1) if b not in (None,0) and c is not None else None)
                pairs.append(dict(seed=seed,load=load,arm=arm,metrics=metrics))
    summary={'jobs':len(rows),'baseline_source':baseline_source,'offered':sum(r['derived_metrics']['offered'] for r in rows),
             'completed':sum(r['derived_metrics']['completed'] for r in rows),
             'unfinished':sum(r['derived_metrics']['unfinished'] for r in rows),
             'failed_jobs':[r['job'] for r in rows if r['status']!='observed'],
             'matched_complete_output_pairs':matched,'output_mismatches':mismatches,
             'partial_prefix_mismatches':prefix_mismatches,'catalog_monotone':catalog.monotone(),
             'pairs':pairs,'runs':[dict(job=r['job'],status=r['status'],error=r['error'],metrics=r['derived_metrics'],raw_sha256=r['raw_sha256']) for r in rows],
             'interpretation':'24 short diagnostic jobs; no confidence-bounded non-regression or native-engine stability proof'}
    write_json(out/'analysis.json',summary)
    render(out,summary)
    return summary


def render(out,analysis):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    groups=defaultdict(list)
    for row in analysis['runs']:
        groups[row['job']['load'],row['job']['arm']].append(row)
    colors={'native':'#5d6875','fcfs':'#c6843b','pressure':'#087e8b'}
    fig,axes=plt.subplots(1,3,figsize=(14,4),layout='constrained')
    for arm,color in colors.items():
        loads=sorted(load for load,a in groups if a==arm)
        for ax,metric,title in zip(axes,('completion_rate_s','restricted_mean_response_s','restricted_mean_ttft_s'),
                                   ('Completed requests / second','Restricted response (seconds)','Restricted TTFT (seconds)')):
            values=[[r['metrics'][metric] for r in groups[load,arm]] for load in loads]
            ax.plot(loads,[statistics.mean(v) for v in values],'o-',label=arm,color=color)
            ax.fill_between(loads,[min(v) for v in values],[max(v) for v in values],color=color,alpha=.1)
            ax.set(xlabel='Offered load / empirical gated capacity',ylabel=title)
    axes[0].legend()
    fig.suptitle('Actual L4 / Qwen Engine · two traces per load · 12-second observations')
    fig.savefig(out/'hardware.png',dpi=160);plt.close(fig)
    lines=['# Actual-engine diagnostic','',analysis['interpretation'], '',
           'The native arm uses ordinary continuous admission. Both other policies impose external cohort gating. All use the same unchanged baseline binary.',
           '', '![All three policies](hardware.png)','',
           '| Load scale | Arm | Completed/s | Unfinished | Restricted response, s | Restricted TTFT, s | Observed p99 gap, ms |',
           '|---:|---|---:|---:|---:|---:|---:|']
    for (load,arm),rows in sorted(groups.items()):
        avg=lambda metric:statistics.mean(r['metrics'][metric] for r in rows)
        lines.append(f"| {load:.2f} | {arm} | {avg('completion_rate_s'):.3f} | {avg('unfinished'):.1f} | {avg('restricted_mean_response_s'):.4f} | {avg('restricted_mean_ttft_s'):.4f} | {1000*avg('observed_p99_gap_s'):.2f} |")
    lines+=['',f"Offered across all jobs: {analysis['offered']}; completed: {analysis['completed']}; unfinished at the observation boundary: {analysis['unfinished']}.",
            f"Failed jobs: {len(analysis['failed_jobs'])}. Complete matched output comparisons: {analysis['matched_complete_output_pairs']}; mismatches: {len(analysis['output_mismatches'])}; partial-prefix mismatches: {len(analysis['partial_prefix_mismatches'])}.",
            f"Empirical duration catalog monotone: {analysis['catalog_monotone']}. This is not a hardware stability certificate.",
            '', '## Limits', '', 'The rate scale is derived from measured gated cohorts, not the capacity of native continuous batching. Two traces and12seconds per job are a transfer diagnostic. Restricted latency includes censored requests but is not their eventual response time. Gap quantiles include observed gaps only. See every per-seed comparison, native A/A result, per-class metric and raw-file hash in analysis.json.',
            '', '## Source provenance', '', 'The GPU bundle contains the exact executed Python source under source/. It predates the later restricted-TTFT reporting addition; this report derives that metric from the immutable token log. The pre-run source hashes, calibration, complete engine config and model/binary/prompt hashes are retained. A first setup-only attempt failed because its process omitted the previously validated CUDA library paths; no measured workload jobs had started. Its log is preserved separately.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
