"""Helpers to set dates and the interactive set-dates command."""
import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from . import date_mapper, exiftool


def has_setfile():
    return shutil.which("SetFile") is not None


def apply_system_time(
        path: Path,
        tag: str,
        dt: datetime,
        dry_run: bool = False
):
    """Apply modification or creation time to ``path``.

    Args:
        path: Path to the file to update.
        tag: User-provided tag to update. One of:
            - File:System:FileModifyDate
            - File:System:FileAccessDate
            - File:System:FileCreateDate
        dt: Datetime to apply (naive datetimes are treated as local time).
        dry_run: When True, print actions instead of performing them.

    On POSIX systems the modification time is set with :func:`os.utime`.
    On macOS, if the ``SetFile`` tool is available, creation time will be
    attempted as well. Failures when calling SetFile are ignored so tests
    don't fail on systems without SetFile.
    """
    if tag in ['File:System:FileModifyDate', 'File:System:FileAccessDate']:
        if dry_run:
            print(f"DRY RUN: would set mtime, atime for {path} to {dt}")
        else:
            ts = dt.timestamp()
            os.utime(path, (ts, ts))
    elif tag == 'File:System:FileCreateDate' and has_setfile():
        try:
            local_str = dt.astimezone().strftime("%m/%d/%Y %H:%M:%S")
            if dry_run:
                print(f"DRY RUN: would run SetFile -d '{local_str}' {path}")
            else:
                subprocess.run(
                    ["SetFile", "-d", local_str, str(path)], check=False)
        except Exception:
            pass


def cmd_set_dates(
    pattern: str,
    dest_tags: Optional[List[str]] = None,
    src_tags: Optional[List[str]] = None,
    backups_path: Optional[Path] = None,
    backups_tags: Optional[List[str]] = None,
    interactive: bool = False,
    show_exiftool: bool = False,
    dry_run: bool = False,
    progress: bool = False,
    update_systime: bool = False,
) -> None:
    """Handle the ``set-dates`` subcommand.

    This function contains the interactive loop over files. Navigation
    commands ('n'/'p') change which file index will be processed by the
    caller of :func:`date_mapper.interactive_choose`.
    Accepts the individual CLI arguments rather than an argparse Namespace.
    """
    # Accept either preprocessed lists/Path or raw strings; be permissive
    if isinstance(dest_tags, str):
        dest_tags = [d.strip() for d in dest_tags.split(",") if d.strip()]
    elif dest_tags is None:
        dest_tags = []

    if isinstance(src_tags, str):
        src_tags = [s.strip() for s in src_tags.split(",") if s.strip()]
    elif src_tags is None:
        src_tags = []

    if backups_tags is None:
        backups_tags = []
    elif isinstance(backups_tags, str):
        backups_tags = [s.strip() for s in backups_tags.split(",") if s.strip()]

    if backups_path and not isinstance(backups_path, Path):
        backups_path = Path(backups_path)

    pattern_path = Path(pattern)
    if pattern_path.is_absolute():
        parent = pattern_path.parent
        name = pattern_path.name
        files = list(parent.glob(name))
    else:
        files = list(Path().glob(pattern))
    files = [f for f in files if f.is_file()]

    i = 0
    while i < len(files):
        file_to_fix = files[i]

        candidates = date_mapper.gather_candidates(
            file_to_fix,
            src_tags=src_tags,
            backups_path=backups_path,
            backups_tags=backups_tags,
        )

        force_interactive = interactive
        if force_interactive or len(candidates) > 1:
            print(f"\nFile: {file_to_fix}")
            if show_exiftool:
                print("EXIFTOOL DUMP:")
                print(exiftool.read_all_tags(file_to_fix))
            chosen = date_mapper.interactive_choose(candidates)
            # interactive_choose may return navigation commands
            if chosen == 'next':
                i += 1
                continue
            if chosen == 'previous':
                i = max(0, i - 1)
                continue
            if chosen == 'quit':
                raise SystemExit(0)
            if chosen is None:
                print(f"SKIPPED {file_to_fix} (no choice)")
                i += 1
                continue
            chosen_dt = chosen
        else:
            chosen_dt = candidates[0][1] if candidates else None

        if chosen_dt:
            date_mapper.apply_destinations(
                file_to_fix,
                dest_tags,
                chosen_dt,
                dry_run=dry_run,
                update_systime=update_systime,
            )
            print(f"APPLIED {file_to_fix} -> {chosen_dt}")
        i += 1
