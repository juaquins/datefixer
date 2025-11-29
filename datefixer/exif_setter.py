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
        preserve_systime: bool = True
):
    """Set multiple EXIF tags using exiftool. `tags` tag->value.

    Note: you can also use `AllDates`, which sets 
    `DateTimeOriginal`, `CreateDate` and `ModifyDate`

    Example:
        `set_exif_tags(Path('a.jpg'), {'AllDates': '2020:01:01 12:00:00'})`

    Parameters:
        preserve_mtime: When True (default), pass exiftool's `-P` flag
            to preserve the file's modification time. Set to False to
            allow exiftool to update the system modified time.
    """
    if not has_exiftool():
        raise RuntimeError("exiftool not found on PATH")
    sub_cmd = 'overwrite_original_in_place' if preserve_systime else 'overwrite_original'
    cmd = ["exiftool", f"-{sub_cmd}"]
    if preserve_systime:
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
