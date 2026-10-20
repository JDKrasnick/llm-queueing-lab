# Cache-aware continuous batching, then RL

This extension leaves the earlier gated project and its negative native-transfer
result intact. The new intervention is directly inside native `PlanStep`, before
the existing cache feasibility planner and token-budget allocator. No outer gate,
prefill budget cap, cache eviction change, or model-prediction oracle is added.

## Fixed policy first

Use actual `MatchPrefix` results and block reference counts. Greedily rank
prefills by `(uncached_tokens + 256 * marginal_block_charge) / (1 + 0.5 *
matching_queued_siblings)`. Charge newly required private blocks and retained
prefix blocks that have not yet been charged by this proposed order. Keep
decodes first and retain normal allocator validation. Give queued requests that
have waited64 planning opportunities precedence over other prefills. This is
not a wall-clock starvation guarantee; unavailable KV can still prevent service.

The native cache planner remains authoritative for actual shared-block charging,
resident cache growth, speculation, fixed state and feasibility. Our ranking is
a heuristic, not an exact optimization of that planner or a throughput theorem.
Its greedy implementation can cost quadratic/cubic host work in queue size;
host CPU and total wall latency are included in measurements.

Four families: retained-prefix reuse, prefix churn, changing prefix locality,
and no-prefix negative control. Two KV capacities32/128 blocks,16rows,
ordinary2,048-token budget,64 requests offered in three short bursts,6-second
fixed observation. Compare the actual baseline, shortest-uncached-prefill
control, cache-aware ordering, and candidate-off/A/A diagnostics.28 jobs.

## Policy-gradient RL second

After the fixed cache screen completes, select a fixed reference using only
that development screen. Collect eight paired reference traces using distinct
training seeds. Train a linear softmax actor with three actions: FIFO,
shortest-uncached-prefill, cache-aware ordering. Duplicate rankings are masked.
Eight observed features describe current queue length, decode mix, cache-hit
fraction, resident-row pressure, block charge, pending-work spread and waiting
age. Future arrivals and eventual output length are absent.

Actions are sampled **inside the actual C++ Engine scheduler**. Log native
states, probabilities and actions. Six updates of four episodes each use actual
GPU returns: response/TTFT/gap costs, burst makespan and explicit regressions
above2%, with a large failure/output-mismatch penalty. Use episodic REINFORCE,
a leave-one-out action-independent baseline, fixed score scaling, gradient norm
clipping and bounded weights. This is actual RL, not tree fitting or simulator
optimization. Finite-difference tests check the masked score gradient.

Freeze the final actor before testing. No retraining on holdout outcomes.
Evaluate two fresh seeds per family/capacity against baseline, shortest, cache
and deterministic learned actor:64 holdout jobs. Preserve every failed/censored
request and output mismatch. No policy is promoted unless there is a material
gain and all declared latency/correctness gates pass against both strong controls.

Total124 measured jobs:28 development/diagnostic,8 training references,
24 actual RL episodes and64 frozen holdout. Bursts can finish inside the fixed
horizon, making completed/horizon equal across policies; therefore also report
64/final-completion-time as **burst throughput**, not sustainable arrival capacity.

## Source and boundaries

- Native worktree: `projects/onnxruntime-genai-cache-rl`, branch
  `research/cache-aware-rl`, based on source3d0d6eb.
- Python/reports: `projects/llm-queueing-lab`, same research branch.
- Research-only native environment variables; no production configuration API.
- Original private KV-cap PR and upstream Microsoft repository are untouched.
- Do not touch `projects/genai-rl-scheduling`, Kaggle or unrelated notebooks.
- Own authorized Safari notebook/account jdk342@cornell.edu only.
- Pre-run source overlays, full Engine test XML, per-process identities,
  all trajectories, returns, updates and frozen-policy weights are retained.

