import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import zipfile


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        while chunk := f.read(1024*1024):
            digest.update(chunk)
    return digest.hexdigest()


def manifest(root):
    root = Path(root)
    tracked = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in (".py", ".toml", ".md", ".json")
                     and not any(x in p.parts for x in (".git", "__pycache__", "results", ".pytest_cache", ".venv")))
    try:
        revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        revision = None
    return {"python":sys.version, "platform":platform.platform(), "git_head":revision,
            "files":{str(p.relative_to(root)):file_hash(p) for p in tracked}}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n")


def snapshot(root, destination, source_manifest):
    root=Path(root)
    with zipfile.ZipFile(destination,"w",zipfile.ZIP_DEFLATED) as archive:
        for name,expected in source_manifest["files"].items():
            data=(root/name).read_bytes()
            if hashlib.sha256(data).hexdigest()!=expected:
                raise RuntimeError(f"Source changed during snapshot: {name}")
            archive.writestr(name,data)
