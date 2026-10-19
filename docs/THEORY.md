# What the mathematics does and does not establish

This project applies queueing-network ideas to an executable, finite-capacity
LLM admission problem. Its theorem concerns the **gated reference model below**.
It is not a theorem about Microsoft's continuous-batching scheduler. The policy
is a standard queue-weighted service-rate construction; novelty is not claimed.

## Model and the implementation boundary

There are K FIFO class queues. Class k has fixed prompt length p_k, fixed
generated length g_k, and a publicly declared output upper bound u_k >= g_k.
The reference model uses deterministic g_k. This is a declared workload class,
not knowledge of the future realization of an arbitrary user's response.

A cohort a is an integer vector with:

    0 < sum_k a_k <= R
    sum_k a_k * ceil((p_k + u_k) / block_size) <= KV_blocks.

Every class fits alone. The feasible set S is finite and downward closed for
nonempty subvectors. All admitted rows reserve their entire maximum context;
prefix caching, copy-on-write, speculative tokens and sliding windows are absent.
This gives progress by construction in this model, at a possible utilization
cost. It does not claim that GenAI's actual cache allocation has this invariant.

The server admits a cohort, performs a prefill barrier, then shrinking decode
batches. The next cohort waits until the current cohort drains. Individual
requests may finish earlier than this boundary. For deterministic action a:

    tau(a) = setup + prefill_token_cost * sum_k a_k p_k
             + sum_{t=1}^{max(g_k : a_k>0)-1} [
                 decode_step_cost
                 + decode_row_cost * sum_{k:g_k>t} a_k
                 + attention_token_cost * sum_{k:g_k>t} a_k (p_k+t)
               ].

Every coefficient is nonnegative and setup > 0. Thus 0 < tau_min <= tau(a) <=
tau_max < infinity, and tau is monotone under adding rows. The implementation
checks monotonicity exhaustively across the finite action set. KV feasibility
uses u_k, not g_k. `token_offsets` supplies the internal publication timeline.

## Exact capacity region of this restricted service family

Let r(a) = a / tau(a). Any long-run service allocation in this gated family has
its rate in the downward closure of conv{r(a): a in S}. Idle time corresponds to
the origin, already in that downward closure. This region bounds feasible
long-run service vectors for this family, not for a more capable continuously
batching engine. A ray bound fixes the class mixture: under overload, a higher
total completion count can coexist with an accumulating backlog in one class.

For two classes, `Catalog.capacity(mix)` computes the largest total arrival rate
lambda with lambda*mix in this region. The optimum lies at a rate vertex or a
two-vertex segment intersection with the balanced-rate line. It returns the
actions and **time fractions** witnessing the bound. Time fractions w_a convert
to probabilities at renewal epochs by p_a proportional to w_a/tau(a). Confusing
these fractions would give an incorrect capacity calculation.

Tests compare the analytic construction to independent dense mixtures of every
pair of rate vectors. A certificate is exact up to ordinary floating arithmetic;
it is not a symbolic proof checker.

## Queue-pressure admission

At each cohort boundary, with currently waiting queue vector Q, choose:

    a*(Q) in argmax_{a in S, a <= Q} Q dot a / tau(a).

Within each class, serve the oldest requests first. Do not wait to fill a cohort.
No future arrivals, workload labels such as "overloaded", or realized future
output lengths enter this decision. Service costs are the known reference
model or a separately frozen empirical calibration. An inaccurate calibration
can produce a poor real policy.

## Single-station stability result (reference model only)

**Proposition.** With independent class-wise Poisson arrivals, exact deterministic
service durations above, and arrival vector strictly inside the gated capacity
region, queue-pressure admission stabilizes the reference model's queue-count
chain at cohort boundaries. This does not establish latency dominance, bounded
individual overtaking, or stability at the boundary of the region.

Proof: at a nonempty decision epoch,

    Q' = Q - a + A(tau(a)),
    V(Q) = (1/2) sum_k Q_k^2.

Independence of future Poisson increments and bounded service times gives

    E[V(Q') - V(Q) | Q] / tau(a)
        <= C + Q dot lambda - Q dot a / tau(a),

where a valid finite constant is

    C = (1/2) sum_k [lambda_k + 2 lambda_k^2 tau_max
                     + 2 R^2 / tau_min].

To compare with the unrestricted finite catalog, take its highest-scoring
action b and truncate it to c_k=min(b_k,Q_k). If nonempty, it is feasible.
Monotonicity gives tau(c)<=tau(b).
Only coordinates Q_k < b_k <= R lose service, so

    Q dot c / tau(c) >= Q dot b / tau(b) - K R^2 / tau_min.

If that particular b truncates to zero, its score itself is bounded by this
constant, and any nonempty available action provides the same inequality.
The implemented available-action maximizer is at least as good as c.
Strict interior membership supplies a convex combination with service vector
r >= lambda + epsilon*1 for some epsilon>0. Therefore

    E[delta V | Q] / tau(a*)
        <= C + K R^2/tau_min - epsilon * sum_k Q_k.

The drift is uniformly negative outside a finite queue-count set. Standard
Foster-Lyapunov reasoning yields positive recurrence of the accessible class
of the queue-count chain. Empty states wait for the next arrival; their mean
idle time is finite when total arrival rate is positive. This also makes the
continuous-time regenerative process stable. QED.

This is an independently stated derivation for a deliberately restricted model;
it should receive mathematical review. It is not represented as a new result
by Dai or as part of the cited paper's proofs.

## Queue area and latency accounting

Pathwise, integral_0^H N(t) dt equals sum over arrivals before H of
min(completion-arrival, H-arrival). Unfinished requests remain in this sum.
Dividing by all offered requests gives a **restricted mean response**, not an
estimate of their eventual mean response under overload. Likewise, the area of
the arrived-but-no-first-token queue gives restricted TTFT. The report currently
shows observed-only TTFT with its censoring count; it does not silently treat
missing first tokens as fast requests.

Backlog-tail slopes and finite-run completion rates are diagnostics, not proofs
of stochastic stability. In particular, an overloaded finite trace can still
drain after arrivals stop. There is no drain phase in reported fixed-horizon
throughput measurements.

## Networks and transfer to an actual engine

`network.py` simulates distinct servers and an actual fork/join dependency DAG:
0 -> {1,2} -> 3. Node 3 is released only when both predecessors finish for the
same root job. All unfinished roots, ready queues, active tasks and blocked join
buffers are retained. Local pressure and downstream-aware backpressure are
**experimental network policies**. No network stability theorem is asserted;
the bounded-overtaking assumptions in related fork/join work are not proved for
our local pressure policy. Cycles are explicitly rejected.

The real-engine adapter controls external admission at the same cohort boundary,
but the internal engine has mixed prefill/decode, real kernels and actual cache
allocation. It therefore has different service times. Calibration records every
feasible action and the model/binary identities. A noisy nonmonotone empirical
table does not satisfy the proposition's monotonicity assumption. Even a
monotone fitted mean table is not a proof about state-dependent hardware timing.

The unchanged native continuous-admission arm is essential: a policy can beat
FCFS gated cohorts while losing to normal Engine batching. Such a result is a
negative transfer result, not a serving improvement to upstream.

## Sources and relation to Dai's research

- Dai, Deng, Li and Peng, [Throughput-Optimal Scheduling Algorithms for LLM
  Inference and AI Agents, v3](https://arxiv.org/html/2504.07347v3). Motivation:
  batch-service networks, stability, finite batch limits, DAG/fork-join routing.
  Their stated models and guarantees must not be silently applied to a different
  engine or to finite KV reservation without checking assumptions.
- Dai and Lin, [Maximum Pressure Policies in Stochastic Processing Networks
  (2005)](https://www.isye.gatech.edu/~dai/publications/daiLin05.pdf). Background
  for queue-pressure control; no claim that its theorem automatically covers
  this implementation.
