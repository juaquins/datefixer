"""Set system file times (macOS/Linux)"""
import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime


def has_setfile():
    return shutil.which("SetFile") is not None


def apply_system_time(path: Path, dt: datetime, dry_run: bool = False):
    """Set file's modification and (on macOS) creation time.

    On macOS, `SetFile` is used to set creation date. For modification
    time we use `os.utime`. On other systems we only set modification
    time.
    """
    ts = dt.timestamp()
    if dry_run:
        print(f"DRY RUN: would set mtime for {path} to {dt}")
    else:
        os.utime(path, (ts, ts))
    # macOS creation time with SetFile (expects local time string)
    if has_setfile():
        try:
            local_str = dt.astimezone().strftime("%m/%d/%Y %H:%M:%S")
            if dry_run:
                print(f"DRY RUN: would run SetFile -d '{local_str}' {path}")
            else:
                subprocess.run(
                    ["SetFile", "-d", local_str, str(path)], check=False
                )
        except Exception:
            pass
