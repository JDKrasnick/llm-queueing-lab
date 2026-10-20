"""Reject inconsistent observations before computing benchmark comparisons."""
import hashlib
import json
import math

from .model import Config
from .workload import trace_hash,validate_trace


def require(condition,message):
    if not condition:raise ValueError(message)


def validate_observation(result,config,horizon,policy,check_trace_hash=True):
    require(math.isfinite(horizon) and horizon>0,'Invalid planned horizon')
    require(result['horizon_s']==horizon,'Observation horizon differs from plan')
    require(Config.from_dict(result['config'])==config,'Observation config differs from plan')
    require(result['policy']==policy,'Observation policy differs from plan')
    require(result['status'] in ('observed','failed'),'Unknown observation status')
    require(result['status']!='observed' or not result.get('cleanup_errors'),'Observed run has cleanup errors')
    require(result['status']!='observed' or result.get('error') is None,'Observed run has an error')
    rows=result['requests']
    trace=[{k:r[k] for k in ('id','arrival','class_id')} for r in rows]
    validate_trace(trace,len(config.classes))
    if check_trace_hash:require(trace_hash(trace)==result['trace_sha256'],'Offered trace hash mismatch')
    for row in rows:
        arrival=row['arrival'];admitted=row.get('admitted');finish=row.get('finish')
        tokens=row['tokens'];times=row['token_times']
        require(arrival<horizon,'Offered request outside horizon')
        require(len(tokens)==len(times),'Token/time count mismatch')
        require(all(isinstance(t,int) and not isinstance(t,bool) for t in tokens),'Invalid output token')
        if admitted is not None:
            require(math.isfinite(admitted) and arrival<=admitted<=horizon,'Invalid admission time')
        require(not times or admitted is not None,'Token before admission')
        last=admitted
        for stamp in times:
            require(math.isfinite(stamp) and last<=stamp<=horizon,'Invalid token timeline')
            last=stamp
        if finish is not None:
            require(admitted is not None and times,'Completion without admission/output')
            require(math.isfinite(finish) and last<=finish<=horizon,'Invalid completion time')
            require(len(tokens)==config.classes[row['class_id']].output_tokens,'Completed output length mismatch')
        if 'output_sha256' in row:
            require(hashlib.sha256(json.dumps(tokens).encode()).hexdigest()==row['output_sha256'],'Output token hash mismatch')
    return trace
