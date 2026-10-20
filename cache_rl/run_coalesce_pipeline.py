from pathlib import Path
import os
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
for script in ('build_coalesce_gpu.py','driver_coalesce.py'):
    code=subprocess.call([sys.executable,str(root/'cache_rl'/script)],cwd=root)
    if code:raise SystemExit(code)
