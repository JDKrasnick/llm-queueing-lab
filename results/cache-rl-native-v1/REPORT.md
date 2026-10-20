# Native cache-aware scheduling and actual-engine RL

All policies operate inside continuous batching. No external cohort gate or prefill-budget cap is used.
These are finite burst workloads; burst throughput is 64/final completion time, not a sustainable arrival-rate result. The plan has two held-out seeds per cell.
recorded manifest consistency only; wheels/source archive absent
Collected training jobs: 24; collected held-out jobs: 64.

| Family | KV blocks | Policy | Burst req/s | Restricted TTFT, ms | Restricted response, ms | Observed p99 gap, ms | Cached prompt tokens | Host CPU, s |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| churn | 32 | baseline | 20.92 | 1361.17 | 1613.86 | 59.10 | 32640 | 3.099 |
| churn | 32 | cache | 21.61 | 1245.07 | 1501.34 | 55.64 | 37248 | 3.001 |
| churn | 32 | rl | 21.66 | 1251.38 | 1501.10 | 56.01 | 36480 | 2.995 |
| churn | 32 | shortest | 21.46 | 1241.66 | 1495.77 | 55.01 | 35968 | 3.023 |
| churn | 128 | baseline | 25.50 | 1102.40 | 1609.59 | 68.99 | 34176 | 2.553 |
| churn | 128 | cache | 26.02 | 976.92 | 1456.06 | 70.38 | 35712 | 2.505 |
| churn | 128 | rl | 26.17 | 973.23 | 1449.60 | 68.14 | 35712 | 2.488 |
| churn | 128 | shortest | 26.16 | 975.55 | 1452.15 | 69.32 | 35712 | 2.491 |
| no_prefix | 32 | baseline | 14.71 | 2019.61 | 2306.02 | 57.97 | 0 | 4.378 |
| no_prefix | 32 | cache | 14.82 | 1798.26 | 2082.59 | 59.40 | 0 | 4.346 |
| no_prefix | 32 | rl | 14.84 | 1790.85 | 2074.49 | 58.81 | 0 | 4.339 |
| no_prefix | 32 | shortest | 14.82 | 1793.73 | 2078.23 | 59.75 | 0 | 4.348 |
| no_prefix | 128 | baseline | 18.32 | 1566.66 | 2273.86 | 68.49 | 0 | 3.530 |
| no_prefix | 128 | cache | 18.22 | 1411.64 | 2107.75 | 71.63 | 0 | 3.550 |
| no_prefix | 128 | rl | 18.23 | 1416.01 | 2110.85 | 70.84 | 0 | 3.546 |
| no_prefix | 128 | shortest | 18.22 | 1416.04 | 2111.01 | 71.72 | 0 | 3.548 |
| phase | 32 | baseline | 26.23 | 954.16 | 1217.73 | 54.48 | 50048 | 2.484 |
| phase | 32 | cache | 25.95 | 923.87 | 1184.07 | 56.05 | 47872 | 2.509 |
| phase | 32 | rl | 26.29 | 894.46 | 1150.60 | 52.58 | 50432 | 2.481 |
| phase | 32 | shortest | 26.40 | 889.97 | 1145.38 | 52.25 | 50432 | 2.470 |
| phase | 128 | baseline | 30.51 | 809.67 | 1217.94 | 70.38 | 48896 | 2.146 |
| phase | 128 | cache | 32.03 | 728.33 | 1131.77 | 67.05 | 52096 | 2.053 |
| phase | 128 | rl | 31.86 | 732.04 | 1137.41 | 68.71 | 52096 | 2.062 |
| phase | 128 | shortest | 31.80 | 730.80 | 1137.43 | 68.27 | 52096 | 2.064 |
| reuse | 32 | baseline | 23.32 | 1136.25 | 1407.34 | 56.47 | 41856 | 2.785 |
| reuse | 32 | cache | 23.88 | 975.02 | 1247.48 | 57.73 | 42624 | 2.725 |
| reuse | 32 | rl | 23.24 | 995.18 | 1258.86 | 54.10 | 42112 | 2.795 |
| reuse | 32 | shortest | 23.14 | 1001.49 | 1264.86 | 58.09 | 42112 | 2.805 |
| reuse | 128 | baseline | 29.04 | 913.17 | 1357.48 | 69.73 | 45056 | 2.250 |
| reuse | 128 | cache | 28.78 | 795.48 | 1224.37 | 69.53 | 45056 | 2.270 |
| reuse | 128 | rl | 28.71 | 787.53 | 1217.49 | 69.38 | 45056 | 2.274 |
| reuse | 128 | shortest | 28.77 | 785.61 | 1219.73 | 70.11 | 45056 | 2.270 |

Actual native RL decisions whose probabilities match the pre-update actor: 1808. Action counts: [726, 763, 319].
Held-out per-trace/control cost flags above 2%: 22. Every flag is retained in analysis.json. A partial checkpoint without held-out jobs has no performance verdict. These flags are point estimates, not confidence-bounded non-regression tests.
Offered/completed across all jobs: 7936/7936. Failed jobs: 0. Paired complete output comparisons: 4352; mismatches: 0.

The training reference is selected from the fixed development screen only. The plan uses 24 actual GPU episodes and six REINFORCE updates; final weights freeze before held-out evaluation. Collected checkpoints, returns and trajectories are retained.
The 64-opportunity age override gives priority; it does not guarantee wall-clock completion. Greedy ranking, prefix matching and host overhead have costs. Engine allocator invariants remain authoritative. See the frozen plan for the pre-run protocol.
Largest matched individual cost for cache versus baseline: TTFT 1308.52 ms later; completion 1312.03 ms later. Better means do not remove these costs.
Largest matched individual cost for rl versus baseline: TTFT 1299.90 ms later; completion 1298.37 ms later. Better means do not remove these costs.
