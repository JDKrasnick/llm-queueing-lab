"""Actual continuous Engine admission; no outer cohort gate or synthetic reward."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

from queueing_lab.hardware import GenAISession
from queueing_lab.model import Config,RequestClass
from queueing_lab.provenance import write_json
from queueing_lab.runtime import run_live


class CacheSession(GenAISession):
    def __init__(self,*args,**kwargs):
        self.request_ids={};self.cached_by_id={}
        super().__init__(*args,**kwargs)

    def submit(self,row):
        tokens=row.get('input_tokens',self.prompts[row['class_id']])
        count=row.get('max_new',32)
        options=self.og.RequestOptions();options.set_max_session_tokens(len(tokens)+64)
        request=self.engine.create_request(options=options)
        turn=self.og.TurnOptions(request)
        turn.set_max_generated_tokens(count);turn.set_min_generated_tokens(count);turn.set_do_sample(False)
        request.begin_turn(self.np.asarray(tokens,dtype=self.np.int32),turn)
        self.request_ids[request]=row.get('id')
        return request

    def step(self):
        out=[];flags=self.og.EngineEventFlags
        for event in self.engine.run(self.events):
            if event.flags & flags.CAPACITY_BLOCKED:out.append((None,'blocked',None))
            if event.flags & flags.FAILED:out.append((event.request,'failed',event.error_code))
            if event.flags & flags.TOKEN:out.append((event.request,'token',event.token))
            if event.flags & flags.TURN_FINISHED:
                request_id=self.request_ids.get(event.request)
                if request_id is not None:self.cached_by_id[request_id]=int(event.usage.cached_prompt_tokens)
                out.append((event.request,'finish',None))
        return out

    def close(self,handle):
        super().close(handle);self.request_ids.pop(handle,None)


def run(args):
    config=Config(classes=(RequestClass('long',1537,32,64),RequestClass('short',769,32,64)),
                  rows=16,blocks=args.blocks,block_size=256)
    session=CacheSession('/content/planner-qwen-paged',config,prefix_caching=True,
        cheapest_prefill_first=args.mode=='shortest' and os.getenv('CACHE_USE_BUILTIN_SHORTEST')=='1')
    encode=lambda text:[int(t) for t in session.tokenizer.encode(text)]
    fill=encode(' A database stores records and indexes support efficient retrieval. '*800)
    prefixes={i:encode(f'Reference group {i}: its database operations and indexing structure. '*600)[:1024] for i in range(8)}
    def prompt(i,length,group=None):
        lead=encode(f'Document {i}: describe its query execution plan. ')
        return ((prefixes[group] if group is not None else [])+lead+fill)[:length]
    # Identical initial retained state in all arms, including no-prefix control.
    for group in range(2):
        req=session.submit(dict(class_id=0,input_tokens=prefixes[group]+fill[:1],max_new=1))
        deadline=time.perf_counter()+30
        while True:
            if time.perf_counter()>deadline:raise TimeoutError('warmup')
            finished=False
            for handle,kind,token in session.step():
                if kind=='failed':raise RuntimeError(token)
                if kind=='finish':session.close(handle);finished=True
            if finished:break
    rng=random.Random(args.seed)
    rows=[]
    for i in range(64):
        kind=0 if i%3 else 1
        length=config.classes[kind].prompt_tokens
        group=None
        if args.family=='reuse':group=i%2 if i%4 else None
        elif args.family=='churn':group=(i//8)%8 if i%4 else None
        elif args.family=='phase':group=(i%2) if i<32 else (2+i%6)
        elif args.family!='no_prefix':raise ValueError(args.family)
        tokens=prompt(i,length,group)
        # The first 32 are simultaneous, followed by two small external bursts.
        offered=0 if i<32 else .12 if i<48 else .24
        offered+=rng.uniform(0,.004)
        rows.append(dict(id=i,class_id=kind,arrival=offered,input_tokens=tokens,max_new=32,
                         prompt_sha256=hashlib.sha256(session.np.asarray(tokens,dtype='<i4').tobytes()).hexdigest(),group=group))
    rows.sort(key=lambda r:(r['arrival'],r['id']))
    print('CACHE_MEASUREMENT_START',file=sys.stderr,flush=True)
    cpu=time.process_time()
    result=run_live(session,config,rows,args.horizon,'native')
    result['host_cpu_s']=time.process_time()-cpu
    result.update(family=args.family,seed=args.seed,blocks=args.blocks,mode=args.mode,provenance=session.provenance)
    # Payload identity is checked separately from the offered-time/class hash.
    result['payload_sha256']=hashlib.sha256(json.dumps([(r['id'],r['prompt_sha256'],r['max_new']) for r in rows],sort_keys=True).encode()).hexdigest()
    for row in result['requests']:
        row['output_sha256']=hashlib.sha256(json.dumps(row['tokens']).encode()).hexdigest()
        row['cached_prompt_tokens']=session.cached_by_id.get(row['id'])
        row.pop('input_tokens')
    write_json(args.output,result)
    print(json.dumps(result['metrics']),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--family',required=True)
    parser.add_argument('--seed',type=int,required=True);parser.add_argument('--blocks',type=int,required=True)
    parser.add_argument('--mode',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--horizon',type=float,default=6)
    run(parser.parse_args())
