"""Wall-clock offered-load coordinator, independent of the inference backend.

Session contract: submit(row) -> handle; step() -> [(handle, kind, token)];
close(handle). A kind is token, finish, blocked or failed. Test sessions are
explicitly labeled; they are never reported as real-engine measurements.
"""

import time

from .metrics import summarize
from .policies import pop_action, select
from .simulator import backlog_samples
from .workload import trace_hash, validate_trace


def run_live(session, config, trace, horizon, policy, catalog=None, clock=time.perf_counter, sleep=time.sleep):
    validate_trace(trace,len(config.classes))
    if horizon <= 0 or policy not in ("native", "fcfs", "pressure"):
        raise ValueError("Invalid live run")
    if policy != "native" and catalog is None:
        raise ValueError("Cohort admission requires a frozen service catalog")
    records = [dict(r,admitted=None,token_times=[],tokens=[],finish=None,error=None)
               for r in trace if r["arrival"] < horizon]
    pending, active, cursor = [], {}, 0
    blocked, polls, failure, cleanup_errors = 0, 0, None, []
    start = clock()

    def submit(row, now):
        row["admitted"] = now
        handle = session.submit(row)
        active[handle] = row

    try:
        while clock()-start < horizon:
            now = clock()-start
            while cursor < len(records) and records[cursor]["arrival"] <= now:
                row = records[cursor]
                cursor += 1
                if policy == "native":
                    submit(row,clock()-start)
                else:
                    pending.append(row)
            if policy != "native" and not active and pending:
                action = select(policy,pending,catalog)
                for row in pop_action(pending,action):
                    submit(row,clock()-start)
            if active:
                events = session.step()
                stamp = clock()-start
                polls += 1
                for handle,kind,token in events:
                    if kind == "blocked":
                        blocked += 1
                        continue
                    if kind == "failed":
                        failure = str(token)
                        if handle in active:
                            active[handle]["error"] = failure
                        break
                    if handle not in active:
                        raise RuntimeError("Unknown request event")
                    row = active[handle]
                    if kind == "token" and stamp <= horizon:
                        row["tokens"].append(int(token))
                        row["token_times"].append(stamp)
                    if kind == "finish":
                        if stamp <= horizon:
                            row["finish"] = stamp
                            expected = config.classes[row["class_id"]].output_tokens
                            if len(row["tokens"]) != expected:
                                failure = f"Output count {len(row['tokens'])} != {expected}"
                        session.close(handle)
                        del active[handle]
                if failure:
                    break
                if not events:
                    sleep(0.0001)
            else:
                # Keep observing through the fixed horizon, including idle tail.
                target = records[cursor]["arrival"] if cursor < len(records) else horizon
                sleep(max(0.00001,min(0.001,target-(clock()-start))))
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        for handle in list(active):
            try:
                session.close(handle)
            except Exception as exc:
                cleanup_errors.append(str(exc))
    samples = backlog_samples(records,horizon,0.1)
    return {"schema":1,"backend":session.label,"policy":policy,"config":config.as_dict(),
            "horizon_s":horizon,"trace_sha256":trace_hash(trace),"requests":records,"backlog":samples,
            "metrics":summarize(records,horizon,samples),"blocked_events":blocked,"polls":polls,
            "status":"failed" if failure else "observed", "error":failure,"cleanup_errors":cleanup_errors,
            "elapsed_wall_s":clock()-start}

