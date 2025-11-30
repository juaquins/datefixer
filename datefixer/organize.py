"""Simple organizer utilities.

Provide helpers to organize media into year/month folders based on inferred
dates from filenames or filesystem timestamps.
"""
from pathlib import Path
import shutil
from datetime import datetime
from typing import Optional

from . import utils


def _infer_date_for_file(path: Path) -> Optional[datetime]:
    # Prefer filename inference, then fallback to file ctime
    dt = utils.infer_from_filename(path.name)
    if dt:
        return dt
    try:
        st = path.stat()
        return datetime.fromtimestamp(st.st_ctime)
    except Exception:
        return None


def organize_by_year(pattern: str, dest_root: Path, dry_run: bool = False):
    """Organize files matching `pattern` into `dest_root` YYYY directories.

    Args:
        pattern: Glob pattern to select files (relative to CWD).
        dest_root: Destination root directory where year/month subdirs will be created.
        dry_run: If True, only print planned moves and do not perform them.

    Returns:
        A list of tuples (src, dst) of planned/made moves.
    """
    matches = list(Path().glob(pattern))
    moves = []
    for p in matches:
        if not p.is_file():
            continue
        dt = _infer_date_for_file(p)
        if not dt:
            continue
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
