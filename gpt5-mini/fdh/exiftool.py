"""Helpers to call exiftool and parse its JSON output."""
import json
import shutil
import subprocess
from pathlib import Path
from .utils import parse_date


def has_exiftool():
    return shutil.which("exiftool") is not None


def read_all_tags(path: Path):
    """Return exiftool JSON dict for the file, or {} if not available."""
    if not has_exiftool():
        return {}
    try:
        r = subprocess.run(
            ["exiftool", "-time:all", "-a", "-G0:1", "-s", "-j", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
        )
        data = json.loads(r.stdout)
        return data[0] if data else {}
    except Exception:
        return {}


def earliest_time_from_exiftool(path: Path):
    obj = read_all_tags(path)
    if not obj:
        return None
    vals = []
    for k, v in obj.items():
        if k == "SourceFile":
            continue
        if isinstance(v, list):
            for s in v:
                dt = parse_date(s)
                if dt:
                    vals.append(dt)
        elif isinstance(v, str):
            dt = parse_date(v)
            if dt:
                vals.append(dt)
    return min(vals) if vals else None
