# Path from research artifact to a maintainable contribution

The current artifact is a standalone project. It has not been submitted upstream,
and the existing private cap PR is unchanged. Do not add this whole laboratory
to a production scheduler diff.

## First possible contribution: offered-load benchmark

Extract a small Engine benchmark that accepts a fixed arrival trace and records
offered/admitted/first-token/finish timestamps, unfinished requests, token hashes
and binary/config provenance. Use normal native admission as the default. This
is useful without changing scheduling behavior, because a fixed backlog and a
fixed arrival-rate workload answer different questions.

Adapt to the current upstream public API before submission. This artifact was
run against the pinned private-study baseline; compatibility with arbitrary
GenAI releases is not claimed. Follow the upstream benchmark conventions and
avoid bringing plotting dependencies into the runtime package. Discuss scope
with maintainers only when the user authorizes contacting them.

## Second possible contribution: a concrete engine-level fix

Use evidence to identify a specific mechanism (for example, feasible queued
work bypassed by a provisional selection, or reservation preventing progress).
Reduce it to an allocator/scheduler test with a small trace. Preserve cache
ownership, shared-prefix accounting, decode priority, stable ties and speculative
semantics. A queueing motivation alone does not justify changing those contracts.

The pressure adapter in this project introduces conservative external cohort
gating. That is a research intervention and can lose to continuous admission.
Do not propose enabling it by default based on gains against gated FCFS. If
native wins, retain that negative result and extract only the benchmark.

## Reviewer-facing evidence

A production PR should contain the minimal mechanism and regression test, plus
a short motivation, explicit predicted behavior, baseline-only measurements,
all material costs, and a link to this separate research artifact. A theorem for
gated batches is not proof of general Engine improvement. No universal
non-regression, production readiness, or default enablement is established here.
