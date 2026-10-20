# Independent validation: native cache scheduling and actual RL

Validate this extension without trusting its author's conclusions. Start with
cache_rl/PLAN.md, cache_rl/COALESCE_PLAN.md, cache_rl/THEORY.md and the completed
results under results/cache-rl-native-v1 and results/cache-coalesce-native-v1.
Read VALIDATION_REPAIRS.md and the sibling independent audit REPORT.md too.
If the coalescing dataset is not present/complete, explicitly mark it pending;
do not infer results from its plan or from the first pilot.

The native worktree is `/Users/fastcheetah/projects/onnxruntime-genai-cache-rl`.
Its base is3d0d6eb1327a959c54f2a41f6741ab9414e50286, with research-only scheduler
hooks and an inline policy header. The first-pilot source overlay is preserved
in native/cache-v1 and in its GPU archive. The coalescing overlay is separate.
Verify executed source hashes before comparing either with current source.

1. Inspect the native patch. Decodes must retain priority, normal token budgets
   must remain unchanged, and the original allocator/reservation must remain
   authoritative. Deferred followers must remain queued, not be dropped from
   accounting. Check that this is not an external cohort-drain barrier.
2. Attack prefix coalescing: exact token comparison instead of hash-only matches;
   cold versus already reusable prefixes; resident requests; leader cancellation,
   failure, rewind and completion; age overrides; individually unserviceable
   prompts; block-size alignment and fixed-state/windowed/multimodal limitations.
   Identify any unsafe or unsupported generalization. A local helper test is
   not a full Engine cancellation/rollback integration test.
3. Independently derive the conditional work-saving identity(q-1)*L and its
   limits. Show a case where less prefill work need not lower elapsed time.
   Verify that no gated-model stability theorem is claimed for this native policy.
4. Audit the RL implementation. It must sample actions inside actual native
   Engine steps, not train from oracle labels or a timing simulator. Recompute
   masked softmax probabilities and score gradients from every logged training
   state and pre-update checkpoint. Reconstruct all six updates and verify the
   frozen holdout actor. Check leave-one-out baseline assumptions, clipping,
   reward penalties, incomplete/corrupt outputs and potential hardware drift.
5. Inspect the action space and observation limits. Distinct rankings can still
   produce identical allocations; do not mistake action counts for changed GPU
   work. Determine whether RL simply recovers a fixed shortest-prefill policy.
   A 24-episode linear actor pilot does not exhaust RL or establish optimality.
6. Verify paired offered arrivals, prompt identities, model/config hashes,
   loaded library paths and every output prefix. Preserve all unfinished/failed
   requests. Recompute burst throughput64/final completion time and distinguish
   it from sustainable arrival capacity and completed/fixed-horizon throughput.
   Repeat the timeline, contradictory-metadata, cleanup, empty-trace and handle
   ownership attacks from the earlier audit against the repaired package.
   Verify retained wheel members against every measured native library, the
   source archive revision/content and build log. The legacy datasets have
   recorded manifest consistency only. A retained build record does not prove
   hermetic reproducibility. Distinguish the lost coalescing run's completion
   checksums from actual evidence collected in its corrected repeat.
7. Compare with both native baseline and shortest-prefill. In the first pilot,
   the shortest control goes through the research helper and has an age override;
   in the coalescing follow-up it uses the baseline binary's existing built-in
   cheapest-prefill flag, with ordinary zero aging. Verify only that intended
   config difference; identify whether any weaker-control comparison exaggerates
   the contribution. Use actual baseline-only gains in public-facing summaries.
8. Report mean and per-request costs, p99 gaps, makespan, cache-hit token counts,
   host CPU and all workloads including no-prefix controls. The first pilot
   already has matched individual delays around1.3seconds despite better means;
   those must not disappear from the conclusion. Treat A/A variation and two
   traces per cell as limited diagnostics, not confidence bounds.
   The corrected coalescing repeat has 77 ms mean extra TTFT for its longer
   prompts and a 1.32 s largest individual delay; RL has 97 ms and 1.37 s.
   Verify those class costs and all plotted cell means independently. Check
   the A/A changes, the stronger control's seven-of-eight mean-TTFT wins, and
   the missing matched ranking-only ablation before assigning causal credit
   to coalescing. These are research results, not default-enablement evidence.
9. Run pytest, native sanitizer/fuzz tests and independent counterexamples.
   Verify full/focused Engine XML counts and skip/disabled distinctions. Hardware
   experiments use only the authorized scheduling Colab notebook in Safari;
   do not touch projects/genai-rl-scheduling, Kaggle or other notebooks. Do not
   interrupt a running collector or overlap competing GPU experiments.

Return supported/falsified/insufficient-evidence verdicts for every main claim,
ranked findings with file:line and minimal repros, and the smallest proposed
fixes. Separate mathematical identities, implementation correctness, measured
performance and general/default-enablement readiness. Do not change code,
publish, push, merge or modify the Microsoft PR before reporting findings.
