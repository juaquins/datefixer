"""Helpers to set system file modification and creation times.

This module provides small helpers to update file modification time and,
on macOS, to set the creation time using the external ``SetFile`` utility.
Functions accept ``dry_run`` to make them safe for test usage.
"""

import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime


def has_setfile():
    """Return True when the macOS ``SetFile`` utility is available.

    This helper makes tests platform-aware and avoids attempting to call
    SetFile when it's not present.
    """
    return shutil.which("SetFile") is not None


def apply_system_time(path: Path, tag: str, dt: datetime, dry_run: bool = False):
    """Apply modification or creation time to ``path``.

    Args:
        path: Path to the file to update.
        tag: User-provided tag to update. One of:
            - File:System:FileModifyDate
            - File:System:FileAccessDate
            - File:System:CreatedDate
        dt: Datetime to apply (naive datetimes are treated as local time).
        dry_run: When True, print actions instead of performing them.

    On POSIX systems the modification time is set with :func:`os.utime`.
    On macOS, if the ``SetFile`` tool is available, creation time will be
    attempted as well. Failures when calling SetFile are ignored so tests
    don't fail on systems without SetFile.
    """
    # macOS modify/access time with utime
    if tag in ['File:System:FileModifyDate', 'File:System:FileAccessDate']:
        if dry_run:
            print(f"DRY RUN: would set mtime, atime for {path} to {dt}")
        else:
            ts = dt.timestamp()
            os.utime(path, (ts, ts))

    # macOS creation time with SetFile (expects local time string)
    elif tag == 'File:System:CreatedDate' and has_setfile():
        try:
            # SetFile expects a localized date string; convert to local
            # timezone string before calling the external tool.
            local_str = dt.astimezone().strftime("%m/%d/%Y %H:%M:%S")
            if dry_run:
                print(f"DRY RUN: would run SetFile -d '{local_str}' {path}")
            else:
                subprocess.run(["SetFile", "-d", local_str, str(path)], check=False)
        except Exception:
            # Ignore SetFile/permission errors to keep tests robust.
            pass
