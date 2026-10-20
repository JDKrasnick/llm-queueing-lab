# Prompt mix: public counts and conditional arithmetic

We counted `Request tokens` in the first two-month `BurstGPT_1.csv` trace,
published by [Wang et al., BurstGPT (KDD 2025)](https://github.com/HPMLL/BurstGPT)
under CC BY 4.0. This is a regional Azure OpenAI service trace containing both
conversation and API requests, not a representative distribution of all LLM use.

## Counts

The [pinned file](https://github.com/HPMLL/BurstGPT/blob/d895a53bb7b8ec137d0d2fe203b335835a78c10a/data/BurstGPT_1.csv)
has 1,429,737 rows. We exclude 25,427 rows with zero request tokens from the
length denominator; positive-length rows remain regardless of response outcome.
Of the remaining **1,404,310 requests**:

- **1,051,791 (74.8974%)** contain at most 769 request tokens.
- **184,362 (13.1283%)** contain 770–1,536 request tokens.
- **168,157 (11.9744%)** contain at least 1,537 request tokens.

Thresholds match our fixture's two prompt sizes; they are not universal
definitions of short and long. BurstGPT supplies token counts for its deployed
models; the fixture uses Qwen tokens. We did not retokenize the trace.
Full counts and arithmetic are saved in
[the generated summary](../results/prompt-mix-burstgpt-v1.json).

## Correct weighting

Let `x` be the long-request fraction, `Bs`/`Bl` baseline mean first-token waits,
and `Ns`/`Nl` new means, all in milliseconds. The percent change in mean wait is:

```text
100 × [(1−x) × (Ns−Bs) + x × (Nl−Bl)] / [(1−x) × Bs + x × Bl]
```

Simply averaging class percentages, `(1−x) × (−45.4%) + x × 6.0%`, instead
weights each class by its request share without accounting for its baseline
waiting time. It approximates the desired result only when baseline class means
are close, and is exact when those baseline means are equal.

Using full-precision cache-aware measurements, baseline short/long means are
1,159.729 / 1,281.643 ms and changes are −526.464 / +77.247 ms. At the public
trace's `x = 0.1197435`, the fixed-effects calculation gives **−38.6752%**
(1,174.328 → 720.154 ms). The analogous RL calculation gives **−38.5010%**.
These are **conditional projections, not measured BurstGPT speedups**.

The actual experiment uses `x = 42/64 = 65.625%`. Its measured pooled mean
falls **10.5086%** with cache-aware scheduling and **9.4669%** with RL.

## Why a real replay is still required

The projection maps every request below 1,537 trace tokens to our 769-token
class, including the untested middle range; it maps all larger requests to
1,537 tokens. It holds measured class waiting times fixed. Scheduling changes
with the mix: queue lengths, batch occupancy, KV residency, prefix reuse,
arrival timing and output lengths all affect those waits. Even preserving
class-specific percentage changes would be an unvalidated assumption.

To establish a real-trace gain, freeze the policies, preserve the trace's
arrival and input/output-length relationships, provide matching tokenized
payloads, scale load to the target engine, and run randomized paired baseline
and candidate measurements. Report class/tail costs as well as mean latency.
The prompt-length statistic motivates that evaluation; it does not validate
transporting the fixture's effects to the trace.

## Reproduce the count

Download the pinned raw file and run the local standard-library analysis:

```bash
curl -fL -o /tmp/BurstGPT_1.csv \
  https://raw.githubusercontent.com/HPMLL/BurstGPT/d895a53bb7b8ec137d0d2fe203b335835a78c10a/data/BurstGPT_1.csv
python3 scripts/analyze_prompt_mix.py /tmp/BurstGPT_1.csv
```

The script verifies SHA-256
`46fc9480ef0b748ecb2b51d512ff08c196b031782cbe6f78e28044d768e86d5a`
before counting, then reads the retained held-out class means. It executes no
downloaded code and runs no GPU experiment. The raw 51 MB trace is not bundled.
