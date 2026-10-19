"""Optional actual ONNX Runtime GenAI Engine, imported only for GPU commands.

The pressure policy controls *external cohort admission*. Native continuous
batching within each cohort remains Microsoft's unchanged implementation.
The native arm admits every offered arrival and is the essential system control.
"""

import hashlib
import json
from pathlib import Path
import statistics
import tempfile
import time

from .model import Catalog, Config
from .provenance import file_hash, write_json
from .runtime import run_live
from .workload import generate, trace_hash


class GenAISession:
    label = "onnxruntime-genai-engine"

    def __init__(self, model_dir, config, provider="cuda", native_budget=2048):
        import numpy as np
        import onnxruntime_genai as og
        try:
            import onnxruntime_ep_cuda as ep
            og.register_execution_provider_library(ep.get_ep_name(),ep.get_library_path())
        except ImportError:
            pass
        self.og,self.np,self.config = og,np,config
        source = Path(model_dir).resolve()
        raw = json.loads((source/"genai_config.json").read_text())
        db = raw["engine"]["dynamic_batching"]
        if db["block_size"] != config.block_size:
            raise ValueError("Model block size differs from experiment reservation")
        # The previous research policy fields are not part of this experiment.
        for key in list(db):
            if key.startswith("prefill_") or key in ("cheapest_prefill_first","gpu_utilization_factor"):
                db.pop(key)
        db.update(num_blocks=config.blocks,max_batch_size=config.rows,
                  max_scheduled_tokens=native_budget,prefix_caching=False)
        self.temp = tempfile.TemporaryDirectory(prefix="queueing-model-")
        variant = Path(self.temp.name)
        for entry in source.iterdir():
            if entry.name != "genai_config.json":
                (variant/entry.name).symlink_to(entry,target_is_directory=entry.is_dir())
        (variant/"genai_config.json").write_text(json.dumps(raw))
        oga_config = og.Config(str(variant))
        oga_config.clear_providers()
        oga_config.append_provider(provider)
        self.model = og.Model(oga_config)
        self.tokenizer = og.Tokenizer(self.model)
        self.engine = og.Engine(self.model)
        self.events = self.engine.create_event_buffer(max(4096,config.rows*4))
        self.prompts = {}
        for i,c in enumerate(config.classes):
            text = " Explain the indexing strategy for a database table with many records. "
            tokens = list(self.tokenizer.encode(text*max(100,c.prompt_tokens)))
            if len(tokens) < c.prompt_tokens:
                raise ValueError("Prompt fill too short")
            self.prompts[i] = np.asarray(tokens[:c.prompt_tokens],dtype=np.int32)
        package = Path(og.__file__).resolve().parent
        self.provenance = {"module":str(og.__file__),"version":getattr(og,"__version__",None),
            "model":str(source),"provider":provider,"engine_config":raw,
            "package_libraries":{p.name:file_hash(p) for p in package.rglob("*") if p.suffix in (".so",".dylib",".pyd")},
            "model_files":{str(p.relative_to(source)):file_hash(p) for p in sorted(source.rglob("*")) if p.is_file()},
            "prompt_sha256":{str(i):hashlib.sha256(a.astype("<i4").tobytes()).hexdigest() for i,a in self.prompts.items()}}
        maps = Path("/proc/self/maps")
        self.provenance["loaded_genai_libraries"] = sorted({line.split()[-1] for line in maps.read_text().splitlines()
            if "genai" in line.lower() and ".so" in line}) if maps.exists() else []

    def submit(self,row):
        c = self.config.classes[row["class_id"]]
        options = self.og.RequestOptions()
        options.set_max_session_tokens(c.prompt_tokens+c.output_bound)
        request = self.engine.create_request(options=options)
        turn = self.og.TurnOptions(request)
        turn.set_max_generated_tokens(c.output_tokens)
        turn.set_min_generated_tokens(c.output_tokens)
        turn.set_do_sample(False)
        request.begin_turn(self.prompts[row["class_id"]],turn)
        return request

    def step(self):
        out = []
        flags = self.og.EngineEventFlags
        for event in self.engine.run(self.events):
            if event.flags & flags.CAPACITY_BLOCKED:
                out.append((None,"blocked",None))
            if event.flags & flags.FAILED:
                out.append((event.request,"failed",event.error_code))
            if event.flags & flags.TOKEN:
                out.append((event.request,"token",event.token))
            if event.flags & flags.TURN_FINISHED:
                out.append((event.request,"finish",None))
        return out

    def close(self,handle):
        handle.close()

    def cohort(self,action,timeout=30):
        active = {}
        start = time.perf_counter()
        hashes = []
        try:
            for i,n in enumerate(action):
                for _ in range(n):
                    active[self.submit({"class_id":i})] = (i,[])
            while active:
                if time.perf_counter()-start > timeout:
                    raise TimeoutError("Calibration cohort stalled")
                for handle,kind,token in self.step():
                    if kind == "failed":
                        raise RuntimeError(f"Engine failure {token}")
                    if kind == "token":
                        active[handle][1].append(int(token))
                    if kind == "finish":
                        i,tokens = active.pop(handle)
                        if len(tokens) != self.config.classes[i].output_tokens:
                            raise RuntimeError("Calibration output count mismatch")
                        hashes.append({"class_id":i,"output_sha256":hashlib.sha256(json.dumps(tokens).encode()).hexdigest()})
                        self.close(handle)
            return time.perf_counter()-start,hashes
        finally:
            for handle in active:
                self.close(handle)


def calibrate(model,config,output,reps=3,provider="cuda"):
    if Path(output).exists():
        raise FileExistsError("Calibration output already exists")
    if reps < 2:
        raise ValueError("At least two calibration replicates required")
    session = GenAISession(model,config,provider)
    catalog = Catalog(config)
    entries = []
    for action in catalog.actions:
        session.cohort(action)  # explicit unmeasured action-specific warmup
        values,hashes = [],[]
        for _ in range(reps):
            elapsed,outputs = session.cohort(action)
            values.append(elapsed)
            hashes.append(outputs)
        entries.append({"action":list(action),"mean_s":statistics.mean(values),"samples_s":values,"outputs":hashes})
        write_json(output,{"schema":1,"backend":session.label,"complete":False,
            "config":config.as_dict(),"provenance":session.provenance,"entries":entries})
        print(f"Calibrated {action}: {statistics.mean(values):.6f}s",flush=True)
    write_json(output,{"schema":1,"backend":session.label,"complete":True,
        "config":config.as_dict(),"provenance":session.provenance,"entries":entries,
        "note":"Empirical gated service means; not a theorem for continuous batching"})


def run_hardware(model,table_path,output,policy,rate,horizon,seed,provider="cuda",pattern="poisson"):
    if Path(output).exists():
        raise FileExistsError("Run output already exists")
    table = json.loads(Path(table_path).read_text())
    if table.get("backend") != GenAISession.label or not table.get("complete"):
        raise ValueError("Require complete actual-engine calibration")
    config = Config.from_dict(table["config"])
    catalog = Catalog(config,{tuple(e["action"]):e["mean_s"] for e in table["entries"]})
    session = GenAISession(model,config,provider)
    # Reject accidental table reuse against another binary, model or engine config.
    for key in ("package_libraries","model_files","engine_config","prompt_sha256","provider"):
        if session.provenance[key] != table["provenance"][key]:
            raise ValueError(f"Calibration/runtime identity mismatch: {key}")
    for i in range(len(config.classes)):
        action = tuple(int(j==i) for j in range(len(config.classes)))
        session.cohort(action)
    trace = generate(rate,horizon,seed,pattern=pattern)
    result = run_live(session,config,trace,horizon,policy,catalog)
    result.update(seed=seed,rate=rate,pattern=pattern,calibration_sha256=file_hash(table_path),
                  provenance=session.provenance,catalog_monotone=catalog.monotone())
    for row in result["requests"]:
        row["output_sha256"] = hashlib.sha256(json.dumps(row["tokens"]).encode()).hexdigest()
    write_json(output,result)
    return result["metrics"]
