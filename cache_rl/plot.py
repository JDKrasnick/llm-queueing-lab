"""All held-out workload cells, baseline-only percentage comparisons."""
from collections import defaultdict
import json
from pathlib import Path
import statistics


def main(directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    out=Path(directory);summary=json.loads((out/'analysis.json').read_text())
    pairs=[r for r in summary['pairs'] if r['job']['stage']=='holdout']
    cells=sorted({(r['job']['family'],r['job']['blocks']) for r in pairs})
    figure,axes=plt.subplots(1,3,figsize=(16,4.7),layout='constrained')
    colors={'shortest':'#627d98',summary.get('heuristic','cache'):'#d79132','rl':'#087e8b'}
    for index,(mode,color) in enumerate(colors.items()):
        for ax,metric,title in zip(axes,('restricted_mean_ttft_s','observed_p99_gap_s','burst_throughput_s'),
            ('First-token latency · lower is better','p99 streaming gap · lower is better','Burst throughput · higher is better')):
            means=[];low=[];high=[]
            for family,blocks in cells:
                selected=[r['against']['baseline'][metric] for r in pairs
                          if (r['job']['family'],r['job']['blocks'],r['job']['mode'])==(family,blocks,mode)]
                values=[r['pct'] for r in selected]
                if not values or any(v is None for v in values):raise ValueError('Incomplete cell; do not plot as a speedup')
                mean=100*(statistics.mean(r['candidate'] for r in selected)/statistics.mean(r['baseline'] for r in selected)-1)
                means.append(mean);low.append(mean-min(values));high.append(max(values)-mean)
            ax.bar(np.arange(len(cells))+(index-1)*.24,means,width=.24,color=color,label=mode)
            ax.errorbar(np.arange(len(cells))+(index-1)*.24,means,yerr=[low,high],fmt='none',ecolor='#303030',capsize=2,lw=.7)
            ax.axhline(0,color='#555',lw=.8);ax.set_title(title,fontsize=10)
            ax.set_xticks(np.arange(len(cells)),[f'{f}\n{b} blocks' for f,b in cells],rotation=45,ha='right',fontsize=8)
            ax.set_ylabel('% change from native baseline')
    axes[0].legend(fontsize=8)
    figure.suptitle('Actual Engine · change in cell means; whiskers span the two paired trace changes')
    figure.savefig(out/'holdout.png',dpi=170);plt.close(figure)

    fig,ax=plt.subplots(figsize=(8,4.6),layout='constrained')
    jobs=json.loads((out/'jobs.json').read_text())
    heldout={}
    for job in jobs:
        if job['stage']=='holdout':
            heldout[job['family'],job['blocks'],job['seed'],job['mode']]=json.loads((out/f"job-{job['id']:03d}.json").read_text())
    for mode in (summary.get('heuristic','cache'),'rl'):
        differences=[]
        for (family,blocks,seed,arm),run in heldout.items():
            if arm!=mode:continue
            base=heldout[family,blocks,seed,'baseline'];reference={q['id']:q for q in base['requests']}
            for q in run['requests']:
                b=reference[q['id']];horizon=run['horizon_s']
                first=q['token_times'][0] if q['token_times'] else horizon
                original=b['token_times'][0] if b['token_times'] else horizon
                differences.append(1000*(min(first,horizon)-min(original,horizon)))
        values=np.sort(differences)
        ax.step(values,np.arange(1,len(values)+1)/len(values),where='post',color=colors[mode],label=mode)
    ax.axvline(0,color='#555',lw=1)
    ax.set(xlabel='Change in restricted TTFT vs the same request under baseline (ms)',
           ylabel='Fraction of offered requests',ylim=(0,1),
           title='Request-level gains and costs · pooled across all held-out cells')
    ax.text(.02,.93,'Left of zero: earlier first token\nRight of zero: later first token',transform=ax.transAxes,fontsize=9,va='top')
    ax.legend(loc='lower right');fig.savefig(out/'request_tradeoff.png',dpi=170);plt.close(fig)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('directory');main(p.parse_args().directory)
