"""Helpers to write EXIF tags using exiftool."""
import shutil
import subprocess
from pathlib import Path


def has_exiftool():
    return shutil.which("exiftool") is not None


def set_exif_tags(
    path: Path,
    tags: dict,
    dry_run: bool = False,
    update_systime: bool = False
):
    """Set multiple EXIF tags using exiftool. `tags` tag->value.

    Note: you can also use `AllDates`, which sets
    `DateTimeOriginal`, `CreateDate` and `ModifyDate`

    Example:
        `set_exif_tags(Path('a.jpg'), {'AllDates': '2020:01:01 12:00:00'})`

    Parameters:
        update_systime: When False (default), attempt to preserve
            system timestamps. This enables exiftool's
            `overwrite_original_in_place` mode (which tries to keep
            creation/birth time when supported) and adds the `-P` flag
            to preserve the file modification time (mtime). When
            True, the function uses `overwrite_original` and allows
            exiftool to update filesystem timestamps.
    """
    if not has_exiftool():
        raise RuntimeError("exiftool not found on PATH")
    # When update_systime is False we try to preserve system timestamps.
    sub_cmd = 'overwrite_original_in_place'
    if update_systime:
        sub_cmd = 'overwrite_original'
    cmd = ["exiftool", f"-{sub_cmd}"]
    if not update_systime:
        # -P preserves the file modification time (mtime)
        cmd.append("-P")
    for tag, val in tags.items():
        cmd.append(f"-{tag}={val}")
    cmd.append(str(path))

    if dry_run:
        # Dry run prints the command instead of executing it so tests and
        # users can verify what would be written without changing files.
        print("DRY RUN:", " ".join(cmd))
        return True

    subprocess.run(cmd, check=True)
    return True
