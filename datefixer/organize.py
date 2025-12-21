"""Simple organizer utilities.

Provide helpers to organize media into year/month folders based on inferred
dates from filenames or filesystem timestamps.
"""
from pathlib import Path
import shutil
from datetime import datetime


def organize_by_year(pattern: str, dest_root: Path, dry_run: bool = False, birthtime_func=None):
    """Organize files matching `pattern` into `dest_root` YYYY directories.

    Args:
        pattern: Glob pattern to select files (relative to CWD).
        dest_root: Destination root directory where year/month subdirs will be
            created.
        dry_run: If True, only print planned moves and do not perform them.

    Returns:
        A list of tuples (src, dst) of planned/made moves.
    """
    matches = list(Path().glob(pattern))
    moves = []
    for p in matches:
        if not p.is_file():
            continue
        # Allow tests to inject a birthtime function for deterministic
        # behavior. If not provided, fall back to the platform-specific
        # `st_birthtime` or finally the modification time.
        if birthtime_func is not None:
            ts = birthtime_func(p)
        else:
            st = p.stat()
            ts = getattr(st, "st_birthtime", None) or getattr(st, "st_mtime", None)
        if ts is None:
            continue
        dt = datetime.fromtimestamp(ts)
        year = f"{dt.year:04d}"
        target_dir = dest_root / year
        target_dir.mkdir(parents=True, exist_ok=True)
        dst = target_dir / p.name
        if dry_run:
            print(f"DRY RUN: would move {p} -> {dst}")
            moves.append((p, dst))
            continue
        shutil.move(str(p), str(dst))
        moves.append((p, dst))
    return moves
