# Frozen evaluation and interpretation

## Synthetic screen v1

Run before inspecting results:

- Configurations: (8 rows,16 blocks), (8 rows,32 blocks), (4 rows,64 blocks).
- Classes: prefill-heavy 768 prompt/16 output/32 output bound; decode-heavy
  64 prompt/128 output/160 output bound. Block size64.
- Arrival patterns: Poisson, ten-at-once Poisson bursts, and a phase switch from
  90% first-class to90% second-class halfway through the observation window.
- Offered load:0.5,0.85,1.05,1.25 times the equal-mixture gated **model** capacity.
  The phase workload does not have a stationary equal class mixture; this label
  is only a common rate scale and is not a stability certificate for that trace.
- Five independent trace seeds20261021..20261025;30s observation; no drain.
- Policies: FCFS with capacity-aware skipping; queue-pressure admission.
-360 runs/180 paired traces; all settings/failures/censored requests retained.
-45 fork/join network runs: same five seeds, three loads0.5/0.85/1.05 and
  FCFS/local pressure/downstream-aware backpressure. Distinct simulated servers.

No policy fitting or hyperparameter search uses these seeds. These are
reproducible model-validation experiments, not an unseen real-world benchmark.

## Hardware screen v1

The adapter uses the unchanged baseline Engine package from the previous
Microsoft study, with a separate config and disabled prefix caching. No cap
patch is installed for this project. Four rows,16blocks,256tokens/block.
Classes769prompt/16output/32bound and65prompt/96output/128bound.
This is a small diagnostic configuration, not a representative production
distribution. Full-context reservation is external and conservative.

Each feasible cohort action receives one unmeasured warmup plus two timed
calibration replicates. The resulting **empirical gated** rate hull scales
three offered loads0.5/0.85/1.05; it is not native Engine capacity. Calibration
finishes before measured arrival traces are generated. Seeds20261101/2 are
held separate from the synthetic screen. Each arm is a fresh process,12s,
Poisson offered arrivals, no drain. Four randomized arms per trace:

1. native: admit offered arrivals directly to the ordinary Engine;
2. native A/A: repeat that control with identical offered arrivals;
3. FCFS gated: admit a feasible cohort and wait for it to drain;
4. pressure gated: select the cohort by the frozen empirical service table.

24 jobs. Compare matched offered arrivals and per-request generated token
sequences. Report all unfinished requests and failures. Differences in prompt
tokens, loaded GenAI libraries, engine config or model files invalidate the
pair. Hardware code rejects calibration/runtime identity mismatches. No
hardware theorem or confidence-bounded non-regression claim follows from two
traces per load. A/A is descriptive, not a universal noise bound.

## Metrics and failure rules

- Throughput: completed requests per fixed wall-clock observation second.
- Backlog: all offered-but-unfinished requests, including the external queue.
- Restricted response: exact queue area / all offered requests, with right
  censoring. It is bounded by the observation duration and not eventual latency.
- TTFT: offered arrival to first published token; currently observed-only with
  missing-token count. Do not compare it without noting censoring differences.
- Streaming gap: elapsed time between successive published tokens from the
  same request; p99 pools observed gaps and has no guarantee for unobserved
  tokens or uncompleted requests.
- Fairness: per-class offered/completed/unfinished and restricted response.
- Network: root completion and response, server queues and blocked join state.
- Status/timeout/output mismatch: retained, never replaced with a fresh seed.

Do not condition headline throughput/response comparisons on both arms
completing all requests. Do not use individual token samples as independent
replicates. Tables retain all cells rather than selecting the biggest gain.

## Upstream decision

This artifact may validate a restricted model while rejecting direct policy
transfer. A production change needs a concrete engine-level mechanism, broader
request mixes, cancellation/early EOS/prefix reuse/speculation tests, overhead
measurements, longer runs and independent hardware. Default enablement requires
a separately agreed regression bar; this study does not establish it.
