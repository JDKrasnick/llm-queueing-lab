# Cache-aware queueing hypothesis and RL objective

The native scheduler chooses an order of pending prefills before the existing
allocator admits feasible rows. Decode priority and token allocation are fixed.
The intervention changes neither model code nor KV ownership rules.

## Cache-aware heuristic

Prompt length alone is a poor service-cost proxy when some prompt KV is already
cached. `MatchPrefix` supplies actual reusable block identities and the remaining
uncached token count. Under memory pressure, adopting an unreferenced retained
block also consumes capacity that the allocator could otherwise reclaim.
That block must be charged once per proposed batch, even if several requests
share it. Private blocks require additional allocation independently.

We rank by uncached work plus a fixed shadow price for marginal KV demand,
divided by a heuristic benefit for queued siblings sharing the same matched
prefix boundary. This approximates a resource-aware queueing decision: favor
requests that can obtain service with less incremental compute/memory pressure.
The price256 and sibling factor0.5 are fixed development choices, not derived
optimal coefficients. Greedy ordering does not solve the combinatorial batch
optimization problem. The actual native allocator validates every admission.

This method is related to prefix-aware scheduling and cache reuse in systems
such as [SGLang](https://arxiv.org/abs/2312.07104); novelty is not claimed.
Unlike the earlier gated model, it allows new admissions while streams remain
active. Unlike the original prefill-cap PR, it does not lower prefill budgets.

## RL policy and credit assignment

The observation is an eight-dimensional function of current queues, prefix
matches, residency and wait ages. A linear actor produces three masked logits:

    pi(a | x) = exp(w_a dot x) / sum_{b in available} exp(w_b dot x).

Actions choose FIFO, shortest-uncached-prefill or the cache-aware heuristic.
When two orderings are identical, duplicate actions are masked. This removes
some false choices, but distinct orderings can still produce the same actual
allocation if capacity/budget dominates. Logged action count is therefore not
a count of changed GPU batches.

Within an actual GPU episode the actor samples at scheduling decisions. The
terminal reward compares response/first-token latency, observed p99 gaps and
burst completion time with a separately measured fixed reference for the same
offered trace. Failures, incomplete output and token mismatches receive a large
penalty. Extra penalties discourage metric losses above2%.

The score-function estimator is:

    gradient J = E[(R - b) * sum_t gradient log pi(a_t | x_t)].

The implementation uses a leave-one-out rollout-batch baseline, fixed1/64 score
scaling, gradient norm clipping and bounded actor weights. Finite differences
independently check the masked log-probability gradient. Native state/action/
probability logs allow verification that the actual C++ actor used the frozen
pre-update parameters. Returns come from actual Engine runs, not a timing model.

This is a small episodic REINFORCE experiment. It is not PPO, a deep network,
an optimal-control solution, or proof that the observation is Markov. Hardware
timing is noisy and sequential rollouts can be correlated. The penalty is a
training preference, **not a guarantee of constraint satisfaction**. Evaluation
against baseline, shortest-prefill and cache-aware controls is separate.

The six-update/24-episode pilot and two held-out seeds per controlled workload
cell cannot establish broad serving superiority or exhaust the possibilities
of RL. Any claimed benefit must retain metric costs, individual request delays,
host overhead, no-prefix controls, exact source identities and output equality.
