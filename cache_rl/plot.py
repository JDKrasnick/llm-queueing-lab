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
                values=[r['against']['baseline'][metric]['pct'] for r in pairs
                        if (r['job']['family'],r['job']['blocks'],r['job']['mode'])==(family,blocks,mode)]
                if not values or any(v is None for v in values):raise ValueError('Incomplete cell; do not plot as a speedup')
                mean=statistics.mean(values);means.append(mean);low.append(mean-min(values));high.append(max(values)-mean)
            ax.bar(np.arange(len(cells))+(index-1)*.24,means,width=.24,color=color,label=mode)
            ax.errorbar(np.arange(len(cells))+(index-1)*.24,means,yerr=[low,high],fmt='none',ecolor='#303030',capsize=2,lw=.7)
            ax.axhline(0,color='#555',lw=.8);ax.set_title(title,fontsize=10)
            ax.set_xticks(np.arange(len(cells)),[f'{f}\n{b} blocks' for f,b in cells],rotation=45,ha='right',fontsize=8)
            ax.set_ylabel('% change from native baseline')
    axes[0].legend(fontsize=8)
    figure.suptitle('Actual continuous-batching Engine · mean and range of two held-out traces per cell')
    figure.savefig(out/'holdout.png',dpi=170);plt.close(figure)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('directory');main(p.parse_args().directory)
