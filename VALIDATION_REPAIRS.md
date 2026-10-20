# Repairs following the independent d147a49 audit

The audit at `../llm-queueing-lab-validation-20261019/REPORT.md` found real
benchmark defects. These repairs apply to the shared package and the native
cache/coalescing repeat. The auditor's snapshot and original raw observations
remain unchanged. The original release archive is preserved separately.

| Audit finding | Change and evidence |
|---|---|
| Contradictory metadata and invalid timelines accepted | A shared validator binds policy, configuration and horizon, checks unique ordered arrivals and finite ordered admission/token/completion times, and checks output counts/hashes. The original hardware reporter additionally regenerates arrivals from planned seed/rate/pattern. Cache analysis validates job semantics and recomputes all metrics from events. Mutation tests reject the reported attacks. |
| Missing wheel/source build chain | Legacy reports now state only recorded manifest consistency. The repeat retains source archive, both wheels, bootstrap, build log and environment/package identities. Its analyzer verifies archive/member hashes and measured libraries against wheel contents. This remains a retained build record, not a hermetic rebuild or independent attestation. |
| Request ownership lost on failure | Failed `begin_turn` closes its newly created request; calibration retains ownership through validation/close and attempts all cleanup. Cache warmup uses `finally`. Fake-backend tests reproduce output/setup failures. |
| Empty Poisson observations rejected | Empty traces are valid, with zero offered/completed/areas and undefined latency means. Both simulator and live coordinator are tested. |
| Post-horizon submissions | The clock is checked before each submission and before every step. Slow fake submissions leave remaining requests offered but unadmitted. A call already in progress can still cross the horizon; observations discard its later events. |
| Unknown events and cleanup errors counted as success | Unknown event kinds fail the run. Cleanup failure marks it failed while retaining all errors. Tests check both paths. |
| Zero-time completion and inconsistent clipping | Explicit `None` checks replace truthiness in response accounting, including network roots. Aggregate and per-class restricted TTFT use the same clipping function. Boundary tests cover zero completion and a token after the horizon. |

The native repeat also records worker setup failures and watchdog timeouts,
retains an incomplete archive on failure, and refuses to overwrite worker
outputs. Its 150-second subprocess watchdog bounds a stuck worker; the standalone
hardware CLI still cannot interrupt a blocking backend call by itself.

The stricter checks accept all 124 saved first-pilot cache/RL jobs and all 24
original hardware jobs. Their measured conclusions do not change. Legacy cache
trace digests included input arrays later omitted from results, so those digests
can only be compared across arms; the repeat additionally stores a reconstructible
canonical offered-trace digest while retaining the input digest and payload hash.

The first coalescing run completed remotely but its archives were lost when
Colab expired before download. Only completion/checksum output survives in
`results/cache-coalesce-lost-run.json`; it supplies no performance evidence.
The repeat keeps the native policies, workload families and seeds unchanged.
Validation repairs were applied before any repeat measurements or fitting.
