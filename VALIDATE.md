# Independent agent validation prompt

You are independently validating a research artifact at:

`/Users/fastcheetah/projects/llm-queueing-lab`

Your job is to try to **disprove its mathematical and experimental claims**.
Do not optimize for agreeing with its author or for producing impressive gains.
Do not change the implementation until you have recorded reproducible findings.
Do not publish, push, merge, contact anyone, or modify the existing Microsoft
PR. Do not touch `projects/genai-rl-scheduling`, Kaggle or unrelated notebooks.

Read README.md, REPORT.md, docs/THEORY.md and docs/EVALUATION.md. Establish the
current file hashes and git status before testing. The available local Python
is `/Users/fastcheetah/.pyenv/versions/3.11.11/bin/python3.11`; create an isolated
environment if needed. Plotting/tests need matplotlib/pytest; core code is stdlib.

1. **Mathematics:** independently derive the finite-action capacity region and
   pressure drift argument. Check action-dependent durations, time fractions
   versus epoch probabilities, empty queues, truncation of unavailable classes,
   monotone durations, Poisson independence and strict-interior assumptions.
   Find a counterexample if possible. Is the proposition correctly limited to
   gated cohorts? Does any description imply an unsupported native-engine or
   fork/join guarantee? Check whether the standard rule is portrayed as novel.
2. **Independent oracles:** write your own capacity solver (LP if available),
   event simulator for small cases and queue-area integration. Do not merely
   duplicate the implementation. Exhaustively compare small catalogs and sample
   extreme class mixtures, rows1/2/16, just-fitting KV bounds and long outputs.
   Check all selected actions are feasible and cannot see future arrivals.
3. **Accounting:** run the tests, then attack right censoring, no-first-token
   requests, a step crossing the observation boundary, failures, early completion,
   simultaneous events, empty idle tails and duplicate/invalid traces. Recompute
   restricted response/TTFT by integrating queue lengths. Distinguish offered
   timestamps from late host submission timestamps. Preserve every failed run.
4. **Networks:** verify per-root DAG routing and task conservation. A join must
   release once and only after both predecessors complete. Check shrinking active
   cohorts, equal-time release/completion events, idle nodes, blocked join counts
   and every unfinished root. Cycles are intentionally unsupported.
5. **Reproduction:** extract source-snapshot.zip into a new directory, verify
   every source hash against its pre-run plan, and rerun the synthetic screen
   into a new output directory. Compare metrics and offered-trace hashes. Run
   stress_model.py and your own genuinely new seeds/longer horizons. Test service
   calibration error, arrival bursts, phase changes and class imbalance. Report
   per-class starvation/latency costs, not only aggregate throughput.
6. **Hardware evidence:** inspect every job and raw token sequence under
   results/hardware-v1, the frozen calibration and its source snapshot. Verify
   model/library/config/prompt identities, randomized arm order, identical offered
   arrivals, completion counts, native A/A variation and all output mismatches.
   Compare pressure with both gated FCFS and unchanged native continuous
   admission. A gain over gated FCFS is not automatically a Microsoft serving
   improvement. Empirical gated capacity is not native Engine capacity. Two seeds
   and12s runs do not prove non-regression or stochastic stability. If new GPU
   work is needed, use only the authorized scheduling notebook in Safari/account
   jdk342@cornell.edu, and do not run old cells or other notebooks. Obtain any
   tool-required confirmation rather than bypassing an approval rejection.
   Also check `baseline-build-provenance.json` binds measured library hashes to
   the baseline wheel and source revision, and distinguish the executed GPU
   source snapshot from later local reporting additions.
7. **Code review:** inspect timeouts, partial results, resource cleanup, module
   identity, calibration validation, configurable paths, output overwrites and
   optional-dependency failures. Check fake-backend tests cannot be mistaken for
   actual-engine measurements. Identify integration limitations and complexity
   as class count/batch limit grows.

Return: a verdict for each main claim (supported / falsified / insufficient
evidence), ranked findings with file:line, minimal repro commands, independent
calculations, all observed costs and the smallest fixes needed. Separate
mathematical validity, implementation correctness, synthetic evidence, actual
hardware evidence and readiness for an upstream contribution. Do not treat a
green test suite as proof of the theorem or of production readiness.
