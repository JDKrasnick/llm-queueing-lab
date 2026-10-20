# Native cache-aware scheduling and actual-engine RL

All policies operate inside continuous batching. No external cohort gate or prefill-budget cap is used.
These are finite burst workloads; burst throughput is 64/final completion time, not a sustainable arrival-rate result. The plan has two held-out seeds per cell.
retained source archive, build log and wheels; measured library hashes verified
Collected training jobs: 24; collected held-out jobs: 64.

| Family | KV blocks | Policy | Burst req/s | Restricted TTFT, ms | Restricted response, ms | Observed p99 gap, ms | Cached prompt tokens | Host CPU, s |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| churn | 32 | baseline | 19.95 | 1405.23 | 1669.91 | 62.39 | 30464 | 3.246 |
| churn | 32 | coalesce | 21.31 | 1271.88 | 1533.47 | 59.83 | 36096 | 3.043 |
| churn | 32 | rl | 21.05 | 1298.63 | 1552.29 | 55.68 | 35712 | 3.079 |
| churn | 32 | shortest | 21.79 | 1116.83 | 1369.53 | 59.45 | 36992 | 2.978 |
| churn | 128 | baseline | 25.44 | 1085.80 | 1593.91 | 71.04 | 35072 | 2.561 |
| churn | 128 | coalesce | 26.16 | 962.65 | 1435.59 | 72.27 | 37888 | 2.490 |
| churn | 128 | rl | 24.94 | 1010.86 | 1503.54 | 74.36 | 34048 | 2.610 |
| churn | 128 | shortest | 25.31 | 927.25 | 1421.43 | 71.27 | 35328 | 2.572 |
| no_prefix | 32 | baseline | 14.38 | 2048.27 | 2343.84 | 57.78 | 0 | 4.477 |
| no_prefix | 32 | coalesce | 14.64 | 1816.89 | 2105.86 | 59.41 | 0 | 4.400 |
| no_prefix | 32 | rl | 14.57 | 1848.98 | 2140.90 | 60.41 | 0 | 4.418 |
| no_prefix | 32 | shortest | 14.64 | 1784.94 | 2051.12 | 59.17 | 0 | 4.397 |
| no_prefix | 128 | baseline | 18.33 | 1554.82 | 2264.88 | 68.80 | 0 | 3.529 |
| no_prefix | 128 | coalesce | 18.01 | 1432.80 | 2134.72 | 72.83 | 0 | 3.589 |
| no_prefix | 128 | rl | 18.02 | 1425.50 | 2126.73 | 73.35 | 0 | 3.588 |
| no_prefix | 128 | shortest | 17.93 | 1431.10 | 2144.52 | 74.33 | 0 | 3.604 |
| phase | 32 | baseline | 26.13 | 943.69 | 1206.95 | 58.40 | 50176 | 2.493 |
| phase | 32 | coalesce | 26.39 | 891.83 | 1151.85 | 54.87 | 50176 | 2.469 |
| phase | 32 | rl | 26.68 | 873.38 | 1141.36 | 55.39 | 51584 | 2.443 |
| phase | 32 | shortest | 28.15 | 840.97 | 1107.97 | 56.96 | 52224 | 2.318 |
| phase | 128 | baseline | 30.67 | 816.56 | 1227.27 | 70.16 | 49792 | 2.136 |
| phase | 128 | coalesce | 32.79 | 706.57 | 1102.95 | 68.65 | 54272 | 1.998 |
| phase | 128 | rl | 31.92 | 726.71 | 1133.17 | 70.63 | 52736 | 2.051 |
| phase | 128 | shortest | 30.73 | 714.89 | 1129.57 | 71.60 | 49664 | 2.130 |
| reuse | 32 | baseline | 23.19 | 1133.46 | 1405.08 | 57.58 | 42112 | 2.802 |
| reuse | 32 | coalesce | 23.31 | 994.00 | 1270.34 | 57.19 | 42368 | 2.789 |
| reuse | 32 | rl | 23.03 | 997.87 | 1264.40 | 54.74 | 41600 | 2.821 |
| reuse | 32 | shortest | 24.75 | 845.31 | 1104.95 | 55.61 | 45056 | 2.631 |
| reuse | 128 | baseline | 28.62 | 930.05 | 1389.51 | 70.30 | 45056 | 2.283 |
| reuse | 128 | coalesce | 28.42 | 799.04 | 1237.79 | 71.53 | 45056 | 2.298 |
| reuse | 128 | rl | 28.51 | 797.04 | 1231.49 | 71.96 | 45056 | 2.290 |
| reuse | 128 | shortest | 28.51 | 736.20 | 1161.12 | 70.35 | 45056 | 2.292 |

Actual native RL decisions whose probabilities match the pre-update actor: 1818. Action counts: [668, 669, 481].
Held-out per-trace/control cost flags above 2%: 46. Every flag is retained in analysis.json. A partial checkpoint without held-out jobs has no performance verdict. These flags are point estimates, not confidence-bounded non-regression tests.
Offered/completed across all jobs: 7936/7936. Failed jobs: 0. Paired complete output comparisons: 4352; mismatches: 0.

The training reference is selected from the fixed development screen only. The plan uses 24 actual GPU episodes and six REINFORCE updates; final weights freeze before held-out evaluation. Collected checkpoints, returns and trajectories are retained.
The 64-opportunity age override gives priority; it does not guarantee wall-clock completion. Greedy ranking, prefix matching and host overhead have costs. Engine allocator invariants remain authoritative. See the frozen plan for the pre-run protocol.
Largest matched individual cost for coalesce versus baseline: TTFT 1322.53 ms later; completion 1461.01 ms later. Better means do not remove these costs.
Largest matched individual cost for rl versus baseline: TTFT 1369.34 ms later; completion 1508.70 ms later. Better means do not remove these costs.
