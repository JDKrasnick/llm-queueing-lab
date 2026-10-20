# Reproduce the native cache/RL experiment

Local evidence checks need Python 3.11+, NumPy and matplotlib; they do not
execute a model or require a GPU:

```bash
python -m cache_rl.analyze results/cache-coalesce-native-v1
python -m cache_rl.replay results/cache-coalesce-native-v1
python -m cache_rl.plot results/cache-coalesce-native-v1
python -m pytest -q
```

The collected data includes exact executed Python files, a seven-file native
overlay, raw worker outputs, actor decisions, checkpoints, and both compiled
GenAI wheels. `build/build-evidence.zip` also contains the baseline source,
bootstrap, build log, model/package manifest and tool versions. The additional
`native/baseline-build-support.zip` retains the bootstrap's SDK headers, copied
unchanged from the checksum-verified bundle uploaded before the build.

To repeat measurements, use a **fresh authorized Linux NVIDIA L4 runtime** with
CUDA installed, network access for public dependencies/model downloads, and no
other GPU work. The bootstrap and driver intentionally use fixed `/content`
paths and refuse existing experiment output directories. They install packages,
build project code and export a public model. This is a real hardware run,
not a local evidence check. It takes substantial time and uses GPU quota.

Place a copy of the full project at `/content/cache-coalesce-lab`. To reproduce
the measured worker version exactly, extract the collected `source-snapshot.zip`
over that copy first; its plan hashes are authoritative. Then prepare the
baseline inputs:

```python
from pathlib import Path
import zipfile

root = Path('/content/cache-coalesce-lab')
evidence = root / 'results/cache-coalesce-native-v1/build/build-evidence.zip'
with zipfile.ZipFile(root / 'native/baseline-build-support.zip') as z:
    z.extractall('/content')
with zipfile.ZipFile(evidence) as z:
    Path('/content/planner-validation/planner-source-baseline.tar.gz').write_bytes(
        z.read('baseline-source.tar.gz'))
```

Run the baseline bootstrap, then the candidate pipeline, serially. Retain their
combined log at the path expected by the build-evidence collector:

```bash
python /content/planner-validation/planner-bootstrap.py > /content/cache-recovery.log 2>&1
# Continue only after the baseline command succeeds.
python /content/cache-coalesce-lab/cache_rl/run_coalesce_pipeline.py >> /content/cache-recovery.log 2>&1
```

The pipeline validates all overlay hashes, builds/tests native code, retains
the wheels/build record, runs 28 fixed/control jobs, eight training references,
24 real-engine training episodes, and 64 frozen held-out jobs. Workload families,
resources and seeds are recorded before fitting. Do not modify them based on
held-out results. Checkpoints are `/content/cache-coalesce-{cache-screen,trained,complete}.zip`;
their `.ready.json` markers appear only after the archive is closed and hashed.

Download the final archive promptly and verify its marker hash before
extraction. A queued `files.download()` call is not proof that a file was saved;
verify the local file. Preserve failures and incomplete archives. Do not rerun
into an existing output directory or silently replace failed observations.

Repeating this procedure produces new hardware timings and learned weights.
It need not reproduce those noisy numbers bit-for-bit. Local reward/update
replay, source hashes, output comparisons and wheel-member checks are exact
checks on the collected run. Build records do not establish a hermetic rebuild.
