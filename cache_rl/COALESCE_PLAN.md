# Cold-prefix coalescing follow-up, then a fresh RL pilot

The first ranking-only cache policy mostly overlaps shortest-prefill ordering.
Its frozen actor selects shortest on1798/1808 recorded training states. This
does not exhaust cache scheduling or RL: the action space cannot prevent
duplicate cold prefills from entering before their shared prefix is computed.

The follow-up changes that admission decision inside continuous batching.
For pure paged prefix-caching models whose block size divides512, compare the
first512 CPU token IDs **exactly**. When matching queued requests have less than
512cached tokens, admit one prefix leader and defer its unallocated followers.
Never drop resident requests or decodes. Once native prefix publication makes
those512tokens reusable, followers are eligible normally. Unrelated requests
remain eligible throughout. Expired64-opportunity followers bypass coalescing.
Do not coalesce individually unserviceable prompts or fixed-state models.

This trades batch parallelism against duplicate compute/KV allocation. It is
not guaranteed better. Exact token equality avoids hash false positives;
native allocator/reservation and cache adoption remain unchanged. No cohort
drain barrier or lower token budget is introduced.

Before launching, freeze new seeds: development20262301, training20262401/2,
held-out20262501/2. Use the same four families/capacities and124-job stage order
as PLAN.md, with coalescing as action2. Actor feature6 now measures the fraction
of candidates coalescing would defer, which is observable before acting.

The fixed shortest control now uses the **existing baseline binary's built-in
cheapest_prefill_first option**, without the research actor/ranking overhead.
It has ordinary zero aging. The actor's shortest action retains the64-step
priority safeguard. Report this distinction; do not weaken the control by
running it through the research helper. Baseline/cache settings otherwise match.

Do not overlap this build or any GPU execution with the first pipeline's held-out
runs. Preserve both datasets, old source overlays and learned policies. No
retuning on either holdout; this follow-up is a new structural hypothesis with
new train/test seeds, not a replacement of unfavorable first-pilot measurements.

## Conditional work-saving argument

If q already-queued requests share an exact block-aligned cold prefix of L
tokens, a leader computes it, publication succeeds, and those blocks stay
reusable until followers adopt them, independent prefills use q*L prefix tokens
where coalesced admission uses L. The avoided prefill work is (q-1)*L tokens.
With disjoint private tails, the same comparison saves (q-1)*(L/block_size)
physical prefix blocks while those requests are resident. Native ownership
counts the adopted shared blocks once; the scheduler does not modify that rule.

These are conditional work/allocation identities, not elapsed-time guarantees.
Coalescing can lower GPU parallelism or delay followers. Cache eviction,
publication refusal, unmatched continuations and other arrivals complicate
the queue trajectory. The experiment must show observed cached-token changes,
completion time, TTFT and streaming gaps; reduced arithmetic work alone is not
accepted as proof of a generally faster scheduler.
