"""Count a pinned public trace and reweight retained class means (not a replay)."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[1]
REVISION = 'd895a53bb7b8ec137d0d2fe203b335835a78c10a'
SHA256 = '46fc9480ef0b748ecb2b51d512ff08c196b031782cbe6f78e28044d768e86d5a'
SOURCE = f'https://raw.githubusercontent.com/HPMLL/BurstGPT/{REVISION}/data/BurstGPT_1.csv'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    digest = hashlib.sha256()
    with args.trace.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != SHA256:
        raise ValueError('Trace differs from the pinned public file')
    counts = {'rows': 0, 'zero_input_tokens': 0, 'positive_input_tokens': 0,
              'le_769': 0, 'from_770_to_1536': 0, 'ge_1537': 0}
    services = {}
    with args.trace.open(newline='') as f:
        for row in csv.DictReader(f):
            tokens = int(row['Request tokens'])
            if tokens < 0:
                raise ValueError('Negative token count')
            counts['rows'] += 1
            if tokens == 0:
                counts['zero_input_tokens'] += 1
                continue
            counts['positive_input_tokens'] += 1
            bucket = 'le_769' if tokens <= 769 else ('ge_1537' if tokens >= 1537 else 'from_770_to_1536')
            counts[bucket] += 1
            service = services.setdefault(row['Log Type'], {'positive_input_tokens': 0, 'ge_1537': 0})
            service['positive_input_tokens'] += 1
            service['ge_1537'] += tokens >= 1537
    assert counts['rows'] == counts['zero_input_tokens'] + counts['positive_input_tokens']
    assert sum(counts[k] for k in ['le_769', 'from_770_to_1536', 'ge_1537']) == counts['positive_input_tokens']
    percent = {k: 100 * counts[k] / counts['positive_input_tokens']
               for k in ['le_769', 'from_770_to_1536', 'ge_1537']}
    analysis_path = ROOT / 'results/cache-coalesce-native-v1/analysis.json'
    analysis = json.loads(analysis_path.read_text())
    runs = [r for r in analysis['runs'] if r['job']['stage'] == 'holdout']
    means = {}
    for mode in ['baseline', 'coalesce', 'rl']:
        selected = [r for r in runs if r['job']['mode'] == mode]
        assert len(selected) == 16
        assert all(r['metrics']['per_class']['0']['offered'] == 42 and
                   r['metrics']['per_class']['1']['offered'] == 22 for r in selected)
        assert all(r['metrics']['completed'] == r['metrics']['offered'] for r in selected)
        means[mode] = {label: 1000 * statistics.mean(
            r['metrics']['per_class'][class_id]['restricted_mean_ttft_s'] for r in selected)
            for label, class_id in [('short', '1'), ('long', '0')]}

    def reweight(x):
        weighted = {mode: (1-x) * value['short'] + x * value['long']
                    for mode, value in means.items()}
        return {'long_fraction': x, 'mean_ttft_ms': weighted,
                'pct_change_from_baseline': {
                    mode: 100 * (weighted[mode] / weighted['baseline'] - 1)
                    for mode in ['coalesce', 'rl']}}

    result = {
        'source_url': SOURCE, 'source_revision': REVISION, 'source_sha256': SHA256,
        'analysis_sha256': hashlib.sha256(analysis_path.read_bytes()).hexdigest(),
        'counts': counts, 'percent_of_positive_input_requests': percent,
        'services': services, 'measured_class_mean_ttft_ms': means,
        'measured_test_mix': reweight(42/64),
        'illustrative_fixed_class_effect_projection': reweight(counts['ge_1537'] / counts['positive_input_tokens']),
        'projection_is_not_a_real_trace_replay': True,
        'projection_assumptions': [
            'Requests below 1537 trace tokens all map to the 769-token fixture class.',
            'Requests at or above 1537 trace tokens all map to the 1537-token fixture class.',
            'Measured per-class waiting times remain fixed despite the new mix.',
            'Trace and fixture tokenizers, cache behavior, outputs and arrivals are not matched.',
        ],
    }
    output = json.dumps(result, indent=2) + '\n'
    if args.output:
        with args.output.open('x') as f:
            f.write(output)
    else:
        print(output, end='')


if __name__ == '__main__':
    main()
