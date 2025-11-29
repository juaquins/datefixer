"""Helpers to write EXIF tags using exiftool."""
import shutil
import subprocess
from pathlib import Path


def has_exiftool():
    return shutil.which("exiftool") is not None


def set_exif_tags(path: Path, tags: dict, dry_run: bool = False):
    """Set multiple exif tags using exiftool. `tags` is mapping tag->value.

    Example:
        `set_exif_tags(Path('a.jpg'), {'AllDates': '2020:01:01 12:00:00'})`
    """
    if not has_exiftool():
        raise RuntimeError("exiftool not found on PATH")

    cmd = ["exiftool", "-overwrite_original"]
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
