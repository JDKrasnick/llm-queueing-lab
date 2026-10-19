# Evidence index

- `screen-v2/`: authoritative 360-run single-server/45-run fork/join synthetic
  screen, complete compact records, source snapshot, all-cell report and figures.
- `stress-v1/`: 36 longer-horizon/service-estimation-error model runs and exact
  pre-run source snapshot. No hardware results are mixed into these numbers.
- `hardware-v1/`: 24 actual Engine GPU jobs, all raw token events, calibration,
  identities, executed source, all-cell report, analysis and transfer hash.
  The runtime directory was named `llm-queueing-lab-gpu-v2` after a setup-only
  failure. That first failure is retained under `hardware-v1/setup-failure/`.
- `development-screen-v1/`: earlier development replay of the same synthetic
  workload plan, before restricted-TTFT accounting/source-snapshot additions.
  It is retained for history and is **not additional independent evidence**.
- `verification.json`: local test, packaging, notebook and frozen-replay checks.

The main artifact's reported experiment count is 465 runs: 360 single-server,
45 network, 36 stress and 24 measured GPU jobs. Calibration cohorts, replay runs
and the duplicate development screen are not counted as independent trials.
