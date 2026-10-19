"""A gated batch-service reference model, with explicit full-context reservation.

This is not a replica of the GenAI continuous-batching scheduler. A cohort has
a prefill barrier, then shrinking decode batches. New cohorts enter only after
the previous cohort drains. The same external admission boundary is available
in the hardware adapter. No realized future output length is used by admission.
"""

from dataclasses import asdict, dataclass
from itertools import product
import hashlib
import json
import math


@dataclass(frozen=True)
class RequestClass:
    name: str
    prompt_tokens: int
    output_tokens: int
    output_bound: int

    def __post_init__(self):
        if not self.name or min(self.prompt_tokens, self.output_tokens, self.output_bound) < 1:
            raise ValueError("Class names and token counts must be positive")
        if self.output_tokens > self.output_bound:
            raise ValueError("Realized output exceeds its declared bound")


@dataclass(frozen=True)
class Config:
    classes: tuple[RequestClass, ...] = (
        RequestClass("prefill", 768, 16, 32),
        RequestClass("decode", 64, 128, 160),
    )
    rows: int = 8
    blocks: int = 32
    block_size: int = 64
    setup_s: float = 0.001
    prefill_token_s: float = 0.000015
    decode_step_s: float = 0.0015
    decode_row_s: float = 0.00012
    attention_token_s: float = 0.00000015

    def __post_init__(self):
        if not self.classes or len({c.name for c in self.classes}) != len(self.classes):
            raise ValueError("Need uniquely named request classes")
        if min(self.rows, self.blocks, self.block_size) < 1:
            raise ValueError("Capacity must be positive")
        if self.rows > 32 or len(self.classes) > 4 or (self.rows + 1) ** len(self.classes) > 100000:
            raise ValueError("Exact action enumeration limited to 100,000 combinations")
        costs = [self.setup_s, self.prefill_token_s, self.decode_step_s,
                 self.decode_row_s, self.attention_token_s]
        if any(not math.isfinite(x) or x < 0 for x in costs) or self.setup_s <= 0:
            raise ValueError("Service costs must be finite/nonnegative with positive setup")
        if any(self.blocks_for(i) > self.blocks for i in range(len(self.classes))):
            raise ValueError("A declared maximum context cannot fit even alone")

    def blocks_for(self, i):
        c = self.classes[i]
        return (c.prompt_tokens + c.output_bound + self.block_size - 1) // self.block_size

    def feasible(self, action):
        return (len(action) == len(self.classes)
                and all(isinstance(n, int) and n >= 0 for n in action)
                and 0 < sum(action) <= self.rows
                and sum(n * self.blocks_for(i) for i, n in enumerate(action)) <= self.blocks)

    def actions(self):
        return tuple(a for a in product(range(self.rows + 1), repeat=len(self.classes)) if self.feasible(a))

    def as_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        data = dict(value)
        data["classes"] = tuple(RequestClass(**x) for x in data["classes"])
        return cls(**data)

    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.as_dict(), sort_keys=True).encode()).hexdigest()


def token_offsets(config, action):
    """Per-class token publication offsets and cohort duration, in seconds.

    All first tokens publish at the prefill barrier. Decode rows retire as
    their declared deterministic class output lengths are reached. Each cost
    term is nonnegative; adding rows cannot shorten any existing token path.
    """
    if not config.feasible(action):
        raise ValueError("Infeasible cohort")
    time = config.setup_s + config.prefill_token_s * sum(
        n * c.prompt_tokens for n, c in zip(action, config.classes, strict=True))
    offsets = {i: [time] for i, n in enumerate(action) if n}
    longest = max(config.classes[i].output_tokens for i in offsets)
    for token in range(1, longest):
        active = [i for i in offsets if config.classes[i].output_tokens > token]
        rows = sum(action[i] for i in active)
        contexts = sum(action[i] * (config.classes[i].prompt_tokens + token) for i in active)
        time += config.decode_step_s + rows * config.decode_row_s + contexts * config.attention_token_s
        for i in active:
            offsets[i].append(time)
    return offsets, time


class Catalog:
    def __init__(self, config, durations=None):
        self.config = config
        self.actions = config.actions()
        expected = {a: token_offsets(config, a)[1] for a in self.actions}
        self.durations = expected if durations is None else dict(durations)
        if self.durations.keys() != expected.keys():
            raise ValueError("Service table must cover every and only feasible action")
        if any(not math.isfinite(t) or t <= 0 for t in self.durations.values()):
            raise ValueError("Durations must be finite and positive")

    def monotone(self):
        return all(self.durations[a] <= self.durations[b] + 1e-12
                   for a in self.actions for b in self.actions
                   if all(x <= y for x, y in zip(a, b, strict=True)))

    def rates(self):
        return {a: tuple(n / self.durations[a] for n in a) for a in self.actions}

    def capacity(self, mix):
        """Exact two-class ray capacity of the downward convex rate hull.

        An optimum is a vertex or an intersection of the balanced-rate line
        with a two-vertex segment. Mixture weights are fractions of *time*,
        not probabilities of selecting actions at renewal epochs.
        """
        if len(mix) != 2 or any(x <= 0 for x in mix) or not math.isclose(sum(mix), 1):
            raise ValueError("Ray certificate currently requires a positive two-class mix summing to one")
        points = list(self.rates().items())
        best = None
        for a, r in points:
            candidates = [(a, r, 1.0)]
            for b, s in points:
                d = (r[0] - s[0]) / mix[0] - (r[1] - s[1]) / mix[1]
                if abs(d) > 1e-14:
                    w = (s[1] / mix[1] - s[0] / mix[0]) / d
                    if 0 <= w <= 1:
                        candidates.append((b, tuple(w*x+(1-w)*y for x,y in zip(r,s)), w))
            for b, rate, w in candidates:
                total = min(rate[i] / mix[i] for i in range(2))
                if best is None or total > best["requests_s"]:
                    best = {"requests_s": total, "action_a": list(a), "action_b": list(b),
                            "time_fraction_a": w, "service_rates": list(rate)}
        return best

