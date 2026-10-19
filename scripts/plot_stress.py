from collections import defaultdict
import json
from pathlib import Path
import statistics


def main(directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=Path(directory)
    rows=json.loads((out/'summary.json').read_text())
    groups=defaultdict(list)
    for row in rows:
        if row['experiment']=='horizon':
            groups[row['horizon'],row['policy']].append(row)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for policy,color in [('fcfs','#6a737d'),('pressure','#087e8b')]:
        horizons=sorted(h for h,p in groups if p==policy)
        for ax,metric in zip(axes,['unfinished','restricted_mean_response_s']):
            ax.plot(horizons,[statistics.mean(r['metrics'][metric] for r in groups[h,policy]) for h in horizons],
                    'o-',label=policy,color=color)
            ax.set_xlabel('Observation horizon (seconds)')
        axes[0].set_ylabel('Unfinished requests at horizon')
        axes[1].set_ylabel('Restricted response (seconds)')
    axes[0].legend()
    fig.suptitle('Longer-run synthetic diagnostic · 85% model capacity · three independent traces')
    fig.savefig(out/'horizon.png',dpi=160);plt.close(fig)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('directory')
    main(parser.parse_args().directory)
