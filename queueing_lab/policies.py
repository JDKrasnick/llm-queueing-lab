"""Policies see current queue state and a frozen service catalog, never arrivals."""

from collections import Counter


def select(policy, waiting, catalog, downstream=None):
    """Return a nonempty feasible action. Entries expose only class_id/arrival/id.

    pressure maximizes sum(Q_i*n_i)/tau(n). backpressure substitutes
    max(Q_i-D_i, 0); its network behavior is experimental, without a theorem.
    FCFS scans the queue and skips only rows that cannot fit remaining KV.
    """
    if not waiting:
        raise ValueError("Cannot select from an empty queue")
    config = catalog.config
    q = Counter(r["class_id"] for r in waiting)
    if policy == "fcfs":
        action = [0] * len(config.classes)
        for row in sorted(waiting, key=lambda r: (r["arrival"], r["id"])):
            candidate = action.copy()
            candidate[row["class_id"]] += 1
            if config.feasible(candidate):
                action = candidate
        return tuple(action)
    if policy not in ("pressure", "backpressure"):
        raise ValueError(f"Unknown policy {policy}")
    weights = [q[i] for i in range(len(config.classes))]
    if policy == "backpressure":
        if downstream is None or len(downstream) != len(weights):
            raise ValueError("Backpressure needs one downstream count per class")
        weights = [max(0, w-d) for w, d in zip(weights, downstream, strict=True)]
    feasible = [a for a in catalog.actions if all(n <= q[i] for i, n in enumerate(a))]
    return max(feasible, key=lambda a: (
        sum(weights[i]*n for i,n in enumerate(a)) / catalog.durations[a],
        sum(a), tuple(-n for n in a)))


def pop_action(waiting, action):
    remaining = list(action)
    selected, keep = [], []
    for row in sorted(waiting, key=lambda r: (r["arrival"], r["id"])):
        i = row["class_id"]
        if remaining[i]:
            remaining[i] -= 1
            selected.append(row)
        else:
            keep.append(row)
    if any(remaining):
        raise ValueError("Action requests nonexistent work")
    waiting[:] = keep
    return selected
