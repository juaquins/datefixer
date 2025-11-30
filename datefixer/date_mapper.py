"""Helpers that map and apply dates for media files.

This module provides helpers to collect candidate datetimes from
EXIF metadata, filesystem timestamps, and reference backups and to
apply chosen datetimes to files (both filesystem times and EXIF tags).

The functions are written to be small and testable; the CLI uses
these helpers so unit tests can exercise logic without running the
console command.
"""

from typing import List, Tuple, Optional
from datetime import datetime
from pathlib import Path
import glob
from . import exiftool, set_times, exif_setter, utils

ALL_FS_TAGS = {
    'File:System:FileAccessDate',
    'File:System:FileModifyDate',
    'File:System:FileInodeChangeDate',
    'File:System:CreatedDate',
}


def system_tag_to_datetime(
        path: Path,
        tag: str
) -> Optional[datetime]:
    """Return a datetime for common filesystem-derived tags.

    Args:
        path: Path to the file to inspect.
        tag: Name of the filesystem tag (e.g. "FileModifyDate").

    Returns:
        A :class:`datetime.datetime` instance or ``None`` if unavailable.
    """
    st = path.stat()

    match tag:
        case 'File:System:FileAccessDate':
            return datetime.fromtimestamp(st.st_atime)  # File Accessed
        case 'File:System:FileModifyDate':
            return datetime.fromtimestamp(st.st_mtime)  # File Modified
        case 'File:System:FileInodeChangeDate':
            return datetime.fromtimestamp(st.st_ctime)  # File Changed
        case 'File:System:CreatedDate':
            return datetime.fromtimestamp(st.st_birthtime)  # File Created
        case _:
            return None


def candidates_for_file(
        path: Path,
        tags: List[str],
        prefix=''
) -> List[Tuple[str, datetime]]:
    if not len(tags) > 0:
        return []
    use_all_tags = tags[0] in ['*', 'ALL']

    candidates = []
    file_exif_tags = exiftool.read_all_tags(path)

    if use_all_tags:
        for tag, dt_str in file_exif_tags.items():
            dt = utils.parse_date(dt_str) if isinstance(dt_str, str) else None
            if dt:
                candidates.append((f"{prefix}{tag}", dt))
        for tag in ALL_FS_TAGS:
            dt = system_tag_to_datetime(path, tag)
            if dt:
                candidates.append((f"{prefix}{tag}", dt))
    else:
        for tag in tags:
            if tag in ALL_FS_TAGS:
                dt = system_tag_to_datetime(path, tag)
                if dt:
                    candidates.append((f"{prefix}{tag}", dt))
            elif tag in file_exif_tags:
                dt_str = file_exif_tags[tag]
                dt = utils.parse_date(dt_str) if isinstance(dt_str, str) else None
                if dt:
                    candidates.append((f"{prefix}{tag}", dt))
    return candidates


def gather_candidates(
    path: Path,
    src_tags: List[str],
    backups_path: Optional[Path] = None,
    backups_tags: Optional[List[str]] = None
) -> List[Tuple[str, datetime]]:
    """Collect candidate datetimes for ``path``.

    The function inspects EXIF metadata (via :func:`exiftool.read_all_tags`),
    filesystem timestamps (via :func:`system_tag_to_datetime`), and optional
    backup files in ``backups_path``. Results are de-duplicated.

    Args:
        path: File to inspect.
        src_tags: List of tag selectors (EXIF or File:System tags).
        backups_path: Folder with reference files to search for matching names.
        backups_tags: List of tag selectors.

    Note:
        To read or write filesystem timestamps explicitly, use the
        ``File:System:`` prefix with one of the following supported tags:
        ``File:System:FileModifyDate``, ``File:System:FileInodeChangeDate``,
        or ``File:System:FileCreateDate``.

    Returns:
        A list of tuples ``(description, datetime)`` describing
        candidate dates.
    """
    # Collect candidate datetimes from EXIF, filesystem, and backup files.
    # Each candidate is a tuple (description, datetime).
    candidates = candidates_for_file(path, src_tags, prefix=f'{path.name}: ')

    # If a reference backups folder is provided, try to find matching
    # filenames under it (recursive) and extract times from those files.
    if backups_path:
        if backups_tags is None:
            backups_tags = ['*']
        matches = glob.glob(
            str(Path(backups_path) / "**" / path.name), recursive=True
        )
        for file in matches:
            candidates += candidates_for_file(
                path, backups_tags,
                prefix=f"backup: {Path(file).relative_to(backups_path)}: "
            )
    return candidates


def apply_destinations(
    path: Path,
    dests: List[str],
    dt: datetime,
    dry_run: bool = False,
    update_systime: bool = False,
):
    """Apply destination tags to `path`.

    update_systime: when True, allow updating system timestamps
        (creation/modification). When False (default), attempt to
        preserve system timestamps where supported.
    """
    for d in dests:
        if d in ALL_FS_TAGS:
            set_times.apply_system_time(path, d, dt, dry_run=dry_run)
        else:
            dt_str = dt.strftime("%Y:%m:%d %H:%M:%S")
            # Call the exif_setter with the modern `update_systime` parameter.
            exif_setter.set_exif_tags(
                path, {d: dt_str}, dry_run=dry_run,
                update_systime=update_systime)


def interactive_choose(
    candidates: List[Tuple[str, datetime]]
) -> Optional[datetime]:
    if not candidates:
        return None
    print("Multiple possible dates found:")
    for i, (desc, dt) in enumerate(candidates):
        print(f"{i}: {desc} -> {dt}")
    print("c: custom date, s: skip, q: quit, n: next, p: prev")
    # current selection index (default 0)
    idx = 0
    while True:
        ans = input(f"Choose index (current {idx}, default {idx}): ").strip().lower()
        if ans == "":
            return candidates[idx][1]
        if ans == "q":
            raise SystemExit(0)
        if ans == "s":
            return None
        if ans == "c":
            custom = input("Enter custom datetime (YYYY-MM-DD HH:MM:SS): ")
            try:
                from datetime import datetime as _dt
                return _dt.strptime(custom, "%Y-%m-%d %H:%M:%S")
            except Exception as e:
                print("Invalid format:", e)
                continue
        if ans == "n":
            idx = (idx + 1) % len(candidates)
            print(f"Selected {idx}: {candidates[idx][0]} -> {candidates[idx][1]}")
            continue
        if ans == "p":
            idx = (idx - 1) % len(candidates)
            print(f"Selected {idx}: {candidates[idx][0]} -> {candidates[idx][1]}")
            continue
        if ans.isdigit():
            new_idx = int(ans)
            if 0 <= new_idx < len(candidates):
                return candidates[new_idx][1]
        print("Invalid choice")
