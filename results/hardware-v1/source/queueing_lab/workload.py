import hashlib
import json
import math
import random


def generate(rate, horizon, seed, mix=(0.5, 0.5), pattern="poisson"):
    if not math.isfinite(rate) or rate <= 0 or not math.isfinite(horizon) or horizon <= 0:
        raise ValueError("Need positive finite rate/horizon")
    if any(x < 0 for x in mix) or not math.isclose(sum(mix), 1):
        raise ValueError("Class probabilities must sum to one")
    if pattern not in ("poisson", "regular", "bursty", "phase"):
        raise ValueError("Unknown arrival pattern")
    rng = random.Random(seed)
    rows, time = [], 0.0
    while True:
        # Bursty: 10 simultaneous arrivals, with Poisson batch arrivals at rate/10.
        batch = 10 if pattern == "bursty" else 1
        time += (1/rate if pattern == "regular" else rng.expovariate(rate/batch))
        if time >= horizon:
            break
        for _ in range(batch):
            probabilities = mix
            if pattern == "phase" and len(mix) == 2:
                probabilities = (0.9, 0.1) if time < horizon/2 else (0.1, 0.9)
            draw, cumulative, kind = rng.random(), 0.0, len(mix)-1
            for i, probability in enumerate(probabilities):
                cumulative += probability
                if draw < cumulative:
                    kind = i
                    break
            rows.append({"id": len(rows), "arrival": time, "class_id": kind})
    return rows


def trace_hash(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_trace(rows, classes):
    if not rows:
        raise ValueError("Empty arrival trace")
    ids = set()
    last = -1.0
    for row in rows:
        if row["id"] in ids or not isinstance(row["id"], int):
            raise ValueError("IDs must be unique integers")
        if not math.isfinite(row["arrival"]) or row["arrival"] < 0 or row["arrival"] < last:
            raise ValueError("Trace must be sorted with finite nonnegative arrivals")
        if not isinstance(row["class_id"], int) or not 0 <= row["class_id"] < classes:
            raise ValueError("Invalid class")
        last = row["arrival"]
        ids.add(row["id"])

