"""Right-censored, offered-arrival metrics; no completed-only speedup claims."""

import math
import statistics


def quantile(values, probability):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered)-1)*probability
    lo = math.floor(index)
    hi = math.ceil(index)
    return ordered[lo] + (ordered[hi]-ordered[lo])*(index-lo)


def summarize(rows, horizon, samples):
    """Observation ends at horizon; incomplete work is retained and censored.

    Restricted mean response time = integral N(t) dt / all offered requests.
    It is NOT the eventual mean latency of unfinished requests.
    """
    offered = [r for r in rows if r["arrival"] < horizon]
    done = [r for r in offered if r.get("finish") is not None and r["finish"] <= horizon]
    ttft = [r["token_times"][0]-r["arrival"] for r in offered
            if r.get("token_times") and r["token_times"][0] <= horizon]
    gaps = [b-a for r in offered for a,b in zip(r.get("token_times", []), r.get("token_times", [])[1:])
            if b <= horizon]
    def response(row):
        finish=row.get('finish')
        return min(horizon if finish is None else finish,horizon)-row['arrival']
    def first_response(row):
        return (min(row['token_times'][0],horizon) if row.get('token_times') else horizon)-row['arrival']
    residence = [response(r) for r in offered]
    first_residence = [first_response(r) for r in offered]
    tail = [(t,n) for t,n in samples if horizon/2 <= t <= horizon]
    if len(tail) > 1:
        mean_t = statistics.mean(t for t,_ in tail)
        mean_n = statistics.mean(n for _,n in tail)
        denominator = sum((t-mean_t)**2 for t,_ in tail)
        slope = sum((t-mean_t)*(n-mean_n) for t,n in tail)/denominator if denominator else None
    else:
        slope = None
    per_class = {}
    for i in sorted({r["class_id"] for r in offered}):
        subset = [r for r in offered if r["class_id"] == i]
        completed = [r for r in done if r["class_id"] == i]
        per_class[str(i)] = {"offered": len(subset), "completed": len(completed),
            "unfinished": len(subset)-len(completed),
            "restricted_mean_response_s": statistics.mean(response(r) for r in subset),
            "restricted_mean_ttft_s":statistics.mean(first_response(r) for r in subset)}
    return {"offered": len(offered), "completed": len(done), "unfinished": len(offered)-len(done),
        "completion_rate_s": len(done)/horizon,
        "restricted_mean_response_s": statistics.mean(residence) if residence else None,
        "restricted_mean_ttft_s":statistics.mean(first_residence) if first_residence else None,
        "first_token_queue_area_request_s":sum(first_residence),
        "queue_area_request_s": sum(residence),
        "observed_mean_ttft_s": statistics.mean(ttft) if ttft else None,
        "ttft_observed": len(ttft), "ttft_censored": len(offered)-len(ttft),
        "observed_p99_gap_s": quantile(gaps, 0.99), "gap_count": len(gaps),
        "backlog_tail_slope_s": slope, "per_class": per_class}
