from bisect import bisect_right
import math

from .metrics import summarize
from .model import Catalog, token_offsets
from .policies import pop_action, select
from .workload import trace_hash, validate_trace


def simulate(config, trace, horizon, policy="fcfs", sample_period=0.5):
    validate_trace(trace, len(config.classes))
    if not math.isfinite(horizon) or horizon <= 0 or sample_period <= 0:
        raise ValueError("Invalid observation window")
    catalog = Catalog(config)
    rows = [dict(r, token_times=[], admitted=None, finish=None) for r in trace if r["arrival"] < horizon]
    waiting, cohorts = [], []
    cursor, time = 0, 0.0
    while time < horizon:
        while cursor < len(rows) and rows[cursor]["arrival"] <= time:
            waiting.append(rows[cursor])
            cursor += 1
        if not waiting:
            if cursor == len(rows):
                break
            time = rows[cursor]["arrival"]
            continue
        action = select(policy, waiting, catalog)
        selected = pop_action(waiting, action)
        offsets, duration = token_offsets(config, action)
        cohorts.append({"start": time, "finish": time+duration, "action": list(action),
                        "ids": [r["id"] for r in selected]})
        for row in selected:
            row["admitted"] = time
            all_tokens = [time+x for x in offsets[row["class_id"]]]
            row["token_times"] = [t for t in all_tokens if t <= horizon]
            if all_tokens[-1] <= horizon:
                row["finish"] = all_tokens[-1]
        time += duration
    # Exact step function of all offered-but-unfinished requests, including arrivals
    # during a service. Sampling does not drive the simulator or arrivals.
    samples = backlog_samples(rows, horizon, sample_period)
    return {"schema": 1, "backend": "synthetic-gated", "policy": policy,
            "config": config.as_dict(), "config_sha256": config.fingerprint(),
            "trace_sha256": trace_hash(trace), "horizon_s": horizon,
            "metrics": summarize(rows, horizon, samples), "backlog": samples,
            "requests": rows, "cohorts": cohorts}


def backlog_samples(rows, horizon, period):
    arrivals = sorted(r["arrival"] for r in rows)
    finishes = sorted(r["finish"] for r in rows if r.get("finish") is not None)
    times = [i*period for i in range(math.floor(horizon/period)+1)]
    if times[-1] < horizon:
        times.append(horizon)
    return [[t, bisect_right(arrivals,t)-bisect_right(finishes,t)] for t in times]

