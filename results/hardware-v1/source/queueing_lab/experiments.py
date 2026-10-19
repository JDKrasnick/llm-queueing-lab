"""Frozen paired screen; capacity comes from the synthetic model, not tuning."""

from dataclasses import replace
import gzip
import json
from pathlib import Path
import statistics

from .model import Catalog, Config
from .network import simulate_network
from .provenance import manifest, write_json
from .simulator import simulate
from .workload import generate


SEEDS = (20261021, 20261022, 20261023, 20261024, 20261025)
LOADS = (0.5, 0.85, 1.05, 1.25)


def compact(result):
    """Token paths are exactly reconstructible from cohort start/action + config.

    Keep every offered request, cohort, censoring result and backlog sample.
    Do not label this compact file a complete per-token raw event log.
    """
    for row in result.get("requests", []):
        tokens = row.pop("token_times")
        row["observed_tokens"] = len(tokens)
        row["first_token"] = tokens[0] if tokens else None
        row["last_token"] = tokens[-1] if tokens else None
    result["encoding"] = "compact; reconstruct synthetic tokens from config/cohorts"
    return result


def run_screen(output, horizon=30.0, seeds=SEEDS, loads=LOADS, patterns=("poisson","bursty","phase")):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    settings = [("kv16_rows8", replace(Config(), blocks=16)),
                ("kv32_rows8", Config()), ("kv64_rows4", replace(Config(), blocks=64, rows=4))]
    plan = {"schema":1,"purpose":"Synthetic model validation, not GPU speedup", "seeds":list(seeds),
            "loads_relative_to_model_capacity":list(loads),"patterns":list(patterns),"horizon_s":horizon,
            "policies":["fcfs","pressure"],"settings":{name:c.as_dict() for name,c in settings},
            "selection":"No policy tuning on these seeds; all settings retained",
            "provenance":manifest(Path(__file__).resolve().parents[1])}
    write_json(out/"plan.json",plan)
    summaries, certificates = [], {}
    with gzip.open(out/"runs.jsonl.gz","wt") as raw:
        for name,config in settings:
            catalog = Catalog(config)
            certificate = catalog.capacity((0.5,0.5))
            certificates[name] = dict(certificate, monotone=catalog.monotone(),
                                      actions=len(catalog.actions),config=config.as_dict())
            for pattern in patterns:
                for load in loads:
                    rate = certificate["requests_s"]*load
                    for seed in seeds:
                        trace = generate(rate,horizon,seed,pattern=pattern)
                        for policy in ("fcfs","pressure"):
                            result = simulate(config,trace,horizon,policy)
                            result.update(setting=name,pattern=pattern,load=load,rate=rate,seed=seed)
                            summaries.append({k:result[k] for k in
                                ("setting","pattern","load","rate","seed","policy","metrics","trace_sha256")})
                            raw.write(json.dumps(compact(result),allow_nan=False)+"\n")
            print(f"Completed {name}: {len(summaries)} cumulative runs",flush=True)
    write_json(out/"certificates.json",certificates)
    write_json(out/"summary.json",summaries)
    pairs = []
    lookup = {(r["setting"],r["pattern"],r["load"],r["seed"],r["policy"]):r for r in summaries}
    for base in summaries:
        if base["policy"] != "fcfs":
            continue
        candidate = lookup[(base["setting"],base["pattern"],base["load"],base["seed"],"pressure")]
        assert base["trace_sha256"] == candidate["trace_sha256"]
        metrics = {}
        for key in ("completion_rate_s","restricted_mean_response_s","observed_mean_ttft_s","observed_p99_gap_s","unfinished"):
            b,c = base["metrics"][key],candidate["metrics"][key]
            metrics[key] = {"baseline":b,"pressure":c,"relative_pct":100*(c/b-1) if b not in (None,0) and c is not None else None}
        pairs.append({k:base[k] for k in ("setting","pattern","load","seed")} | {"metrics":metrics})
    write_json(out/"pairs.json",pairs)
    # A genuine simulated fork/join DAG; local policy and routing effects are separated.
    network_runs = []
    for seed in seeds:
        for load in (0.5,0.85,1.05):
            rate = certificates["kv32_rows8"]["requests_s"]*load
            trace = generate(rate,horizon,seed)
            for policy in ("fcfs","pressure","backpressure"):
                result = simulate_network(Config(),trace,horizon,policy)
                result.update(seed=seed,load=load,rate=rate)
                network_runs.append(result)
    with gzip.open(out/"network.jsonl.gz","wt") as f:
        for result in network_runs:
            f.write(json.dumps(result,allow_nan=False)+"\n")
    write_json(out/"network-summary.json",[{k:r[k] for k in ("policy","seed","load","rate","metrics")} for r in network_runs])
    return {"single_station_runs":len(summaries),"paired_traces":len(pairs),"network_runs":len(network_runs)}

