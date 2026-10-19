"""Longer horizons and service-model mismatch, declared before running.

Keeps the policy fixed. Arrival seeds differ from the main screen. This script
tests finite-run scaling, not an independent mathematical proof of stability.
"""

from dataclasses import replace
import json
from pathlib import Path

from queueing_lab.model import Catalog, Config
from queueing_lab.provenance import manifest, snapshot, write_json
from queueing_lab.simulator import simulate
from queueing_lab.workload import generate


def main(output):
    out=Path(output); out.mkdir(parents=True,exist_ok=False)
    config=Config(); capacity=Catalog(config).capacity((.5,.5))["requests_s"]
    plan={"horizons":[30,120,480],"seeds":[20261201,20261202,20261203],"load":.85,
          "mismatch_multipliers":[.5,1,2],"purpose":"Finite-run scaling and frozen service-cost sensitivity",
          "source":manifest(Path(__file__).resolve().parents[1])}
    write_json(out/'plan.json',plan)
    snapshot(Path(__file__).resolve().parents[1],out/'source-snapshot.zip',plan['source'])
    results=[]
    for seed in plan['seeds']:
        for horizon in plan['horizons']:
            trace=generate(capacity*.85,horizon,seed)
            for policy in ('fcfs','pressure'):
                r=simulate(config,trace,horizon,policy)
                results.append(dict(experiment='horizon',seed=seed,horizon=horizon,policy=policy,metrics=r['metrics'],trace_sha256=r['trace_sha256']))
    # Same actual model and arrival trace; only the decision catalog is misspecified.
    for multiplier in plan['mismatch_multipliers']:
        estimate=replace(config,prefill_token_s=config.prefill_token_s*multiplier,
                         decode_step_s=config.decode_step_s/multiplier)
        for seed in plan['seeds']:
            trace=generate(capacity*.85,120,seed)
            for policy in ('fcfs','pressure'):
                r=simulate(config,trace,120,policy,decision_catalog=Catalog(estimate))
                results.append(dict(experiment='mismatch',multiplier=multiplier,seed=seed,horizon=120,policy=policy,metrics=r['metrics'],trace_sha256=r['trace_sha256']))
    write_json(out/'summary.json',results)
    print(json.dumps({'runs':len(results),'output':str(out)}))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    main(parser.parse_args().output)
