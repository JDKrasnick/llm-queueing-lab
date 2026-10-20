"""Generate README figures from retained held-out measurements.

Run from the repository root: .venv/bin/python scripts/plot_readme.py
"""
from pathlib import Path
import json
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'results/cache-coalesce-native-v1/analysis.json'
OUT = ROOT / 'docs/figures'
COLORS = {'baseline': '#8493A5', 'coalesce': '#087F82', 'rl': '#5064C4'}
LABELS = {'baseline': 'Normal baseline', 'coalesce': 'Cache-aware', 'rl': 'RL'}
INK = '#1C2B3B'
MUTED = '#536578'


def main():
    data = json.loads(DATA.read_text())
    runs = [r for r in data['runs'] if r['job']['stage'] == 'holdout']
    pairs = [r for r in data['pairs'] if r['job']['stage'] == 'holdout']
    assert len(runs) == 64
    assert all(r['metrics']['completed'] == r['metrics']['offered'] == 64
               for r in runs)
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 12, 'text.color': INK,
        'axes.labelcolor': MUTED, 'xtick.color': MUTED, 'ytick.color': INK,
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.spines.left': False, 'axes.spines.bottom': False,
        'figure.facecolor': '#FAFBFD', 'axes.facecolor': '#FAFBFD',
        'savefig.facecolor': '#FAFBFD',
    })

    # Every class has the same offered count in each trace, so the mean of
    # trace means equals the pooled request mean. No censored requests remain.
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.5), sharex=True)
    fig.subplots_adjust(left=.14, right=.97, top=.70, bottom=.22, wspace=.43)
    fig.text(.04, .91, 'Short prompts start sooner. Long prompts wait longer.',
             fontsize=21, weight='bold')
    fig.text(.04, .84, 'Mean time to first token across all held-out workloads | Lower is better',
             fontsize=12, color=MUTED)
    for ax, class_id, title in zip(axes, ('1', '0'),
            ('Shorter prompts · 769 tokens', 'Longer prompts · 1,537 tokens')):
        means = {}
        for mode in LABELS:
            selected = [r['metrics']['per_class'][class_id] for r in runs
                        if r['job']['mode'] == mode]
            assert len(selected) == 16
            assert len({r['offered'] for r in selected}) == 1
            means[mode] = statistics.mean(r['restricted_mean_ttft_s']
                                         for r in selected) * 1000
        for y, mode in enumerate(LABELS):
            value = means[mode]
            ax.barh(y, value, height=.52, color=COLORS[mode], zorder=3)
            label = f'{value:,.0f} ms'
            if mode != 'baseline':
                label += f'\n({100 * (value / means["baseline"] - 1):+.1f}%)'
            ax.text(value + 28, y, label, va='center', fontsize=12,
                    weight='bold' if mode != 'baseline' else 'normal')
        ax.set_title(title, loc='left', pad=17, fontsize=14, weight='bold')
        ax.set_yticks(range(3), LABELS.values())
        ax.invert_yaxis()
        ax.set_xlim(0, 2100)
        ax.set_xticks([0, 500, 1000, 1500])
        ax.set_xlabel('First-token wait (ms)', labelpad=12)
        ax.tick_params(axis='both', length=0)
        ax.grid(axis='x', color='#DFE5ED', zorder=0)
    fig.text(.04, .07, 'Same 32 output tokens for both classes. 16 held-out traces per policy; descriptive means, not confidence bounds.',
             fontsize=10, color=MUTED)
    fig.savefig(OUT / 'first-token-tradeoff.png', dpi=180)
    plt.close(fig)

    metrics = [
        ('restricted_mean_ttft_s', 'First-token latency', -1),
        ('restricted_mean_response_s', 'Completion latency', -1),
        ('observed_p99_gap_s', 'p99 streaming gap', -1),
        ('burst_throughput_s', 'Burst throughput', 1),
    ]
    families = {'reuse': 'prefix reuse', 'churn': 'cache churn',
                'phase': 'warm to cold', 'no_prefix': 'no shared prefix'}
    fig, ax = plt.subplots(figsize=(12.8, 6.2))
    fig.subplots_adjust(left=.22, right=.96, top=.73, bottom=.21)
    fig.text(.04, .91, 'Strongest measured gains against normal baseline',
             fontsize=21, weight='bold')
    fig.text(.04, .85, 'Selected best workload for each metric | These gains do not all occur together',
             fontsize=12, color=MUTED)
    for index, (metric, label, direction) in enumerate(metrics):
        for mode, offset in [('coalesce', -.17), ('rl', .17)]:
            selected = [r for r in pairs if r['job']['mode'] == mode]
            cells = sorted({(r['job']['family'], r['job']['blocks']) for r in selected})
            candidates = []
            for family, blocks in cells:
                cell = [r['against']['baseline'][metric] for r in selected
                        if (r['job']['family'], r['job']['blocks']) == (family, blocks)]
                assert len(cell) == 2
                baseline = statistics.mean(r['baseline'] for r in cell)
                candidate = statistics.mean(r['candidate'] for r in cell)
                gain = direction * 100 * (candidate / baseline - 1)
                candidates.append((gain, family, blocks))
            gain, family, blocks = max(candidates)
            y = index + offset
            ax.barh(y, gain, height=.27, color=COLORS[mode], zorder=3,
                    label=LABELS[mode] if index == 0 else None)
            ax.text(gain + .25, y, f'{gain:.1f}% · {families[family]} / {blocks} blocks',
                    va='center', fontsize=11)
    ax.set_yticks(range(4), [label for _, label, _ in metrics])
    ax.invert_yaxis()
    ax.set_xlim(0, 22)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.xaxis.set_major_formatter(PercentFormatter(100, decimals=0))
    ax.set_xlabel('Improvement: lower latency or higher burst throughput', labelpad=12)
    ax.tick_params(axis='both', length=0)
    ax.grid(axis='x', color='#DFE5ED', zorder=0)
    ax.legend(loc='lower right', frameon=False, bbox_to_anchor=(1, 1.02), ncol=2)
    fig.text(.04, .09, 'Two held-out traces per workload/capacity. KV blocks measure available cache space; small changes need more repetitions.',
             fontsize=10, color=MUTED)
    fig.text(.04, .045, 'One L4 GPU, Qwen2.5-0.5B-Instruct INT4. Burst throughput is not a measurement of sustainable serving capacity.',
             fontsize=10, color=MUTED)
    fig.savefig(OUT / 'best-measured-gains.png', dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    main()
