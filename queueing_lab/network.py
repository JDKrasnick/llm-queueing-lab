"""Independent simulated servers with DAG routing and real fork/join barriers.

Logical parallelism uses separate simulated clocks/resources. It does not
pretend that several models running serially on one GPU are parallel servers.
The single-station theorem is not claimed for these network policies.
"""

import heapq

from .model import Catalog, token_offsets
from .policies import pop_action, select
from .workload import trace_hash, validate_trace


def simulate_network(config, trace, horizon, policy="fcfs", edges=((1,2), (3,), (3,), ())):
    validate_trace(trace, len(config.classes))
    if horizon <= 0 or not edges:
        raise ValueError("Positive horizon and nonempty DAG required")
    count = len(edges)
    parents = [set() for _ in edges]
    for source, targets in enumerate(edges):
        if len(set(targets)) != len(targets):
            raise ValueError("Duplicate edge")
        for target in targets:
            if not source < target < count:
                raise ValueError("Nodes must be topologically ordered; cycles are rejected")
            parents[target].add(source)
    roots = [i for i,p in enumerate(parents) if not p]
    sinks = {i for i,e in enumerate(edges) if not e}
    if roots != [0]:
        raise ValueError("Network must have exactly one source, node zero")
    catalog = Catalog(config)
    queues = [[] for _ in edges]
    busy = [False]*count
    active_counts = [[0]*len(config.classes) for _ in edges]
    jobs = {r["id"]: dict(r, done=set(), launched=set(), finish=None) for r in trace if r["arrival"] < horizon}
    heap, sequence, history, task_log = [], 0, [], []

    def event(time, kind, data):
        nonlocal sequence
        sequence += 1
        heapq.heappush(heap, (time, sequence, kind, data))

    def enqueue(job, node, now):
        if node in job["launched"]:
            return
        job["launched"].add(node)
        queues[node].append({"id": job["id"]*count+node, "root_id": job["id"],
                             "class_id": job["class_id"], "arrival": now})

    for job in jobs.values():
        event(job["arrival"], "arrival", job["id"])
    while heap and heap[0][0] <= horizon:
        now = heap[0][0]
        # Process all same-time completions/arrivals before making decisions.
        while heap and heap[0][0] == now:
            _,_,kind,data = heapq.heappop(heap)
            if kind == "arrival":
                enqueue(jobs[data], 0, now)
            elif kind == "release":
                busy[data] = False
            else:
                node, row = data
                active_counts[node][row["class_id"]] -= 1
                job = jobs[row["root_id"]]
                job["done"].add(node)
                for target in edges[node]:
                    if parents[target] <= job["done"]:
                        enqueue(job, target, now)
                if sinks <= job["done"]:
                    job["finish"] = now
        for node in range(count):
            if busy[node] or not queues[node]:
                continue
            downstream = [sum(sum(r["class_id"] == i for r in queues[target]) + active_counts[target][i]
                              for target in edges[node]) for i in range(len(config.classes))]
            action = select(policy, queues[node], catalog, downstream)
            selected = pop_action(queues[node], action)
            offsets, duration = token_offsets(config, action)
            busy[node] = True
            active_counts[node] = list(action)
            event(now+duration, "release", node)
            for row in selected:
                finish = now+offsets[row["class_id"]][-1]
                task_log.append(dict(row, node=node, admitted=now, finish=finish))
                event(finish, "completion", (node,row))
        blocked_joins = sum(1 for j in jobs.values() for n in range(count)
            if len(parents[n]) > 1 and n not in j["launched"] and bool(parents[n] & j["done"]))
        history.append({"time":now, "queues":[len(q) for q in queues],
                        "in_service":[sum(a) for a in active_counts], "blocked_joins":blocked_joins,
                        "unfinished_roots":sum(j["arrival"] <= now and j["finish"] is None for j in jobs.values())})
    records = [dict(id=j["id"], class_id=j["class_id"], arrival=j["arrival"], finish=j["finish"],
                    completed_nodes=sorted(j["done"]), launched_nodes=sorted(j["launched"])) for j in jobs.values()]
    completed = sum(r["finish"] is not None for r in records)
    area = sum(min(horizon if r['finish'] is None else r['finish'],horizon)-r['arrival'] for r in records)
    return {"schema":1, "backend":"synthetic-network", "policy":policy, "edges":edges,
            "config":config.as_dict(), "trace_sha256":trace_hash(trace), "horizon_s":horizon,
            "metrics":{"offered_roots":len(records), "completed_roots":completed,
                       "unfinished_roots":len(records)-completed, "completion_rate_s":completed/horizon,
                       "root_queue_area_s":area, "restricted_mean_response_s":area/len(records) if records else None},
            "jobs":records, "tasks":task_log, "history":history}
