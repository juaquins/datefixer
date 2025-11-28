"""Simple FFmpeg wrapper to compress videos and preserve metadata."""
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from .set_times import apply_system_time


def has_ffmpeg():
    return shutil.which("ffmpeg") is not None


def transcode_video(
    src: Path,
    dst: Path,
    crf: int = 28,
    max_width: int | None = None,
    dry_run: bool = False,
    move_original_to: Path | None = None,
):
    """Transcode with reasonable defaults, map metadata, and set dst times.

    Returns True on success. Does not raise on ffmpeg failure.
    """
    if not has_ffmpeg():
        raise RuntimeError("ffmpeg not found on PATH")

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-map_metadata",
        "0",
        "-c:v",
        "libx265",
        "-pix_fmt",
        "yuv420p",
        "-x265-params",
        "no-info=1:log-level=error",
        "-crf",
        str(crf),
        "-preset",
        "medium",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-c:s",
        "copy",
        "-map",
        "0:v?",
        "-map",
        "0:a?",
        "-map",
        "0:s?",
    ]
    if dst.suffix.lower() == ".mp4":
        cmd += ["-tag:v", "hvc1", "-brand", "mp42", "-movflags", "+faststart"]

    if max_width:
        cmd += ["-vf", f"scale=min({max_width},iw):-2"]

    cmd.append(str(dst))

    if dry_run:
        print("DRY RUN:", " ".join(cmd))
        return True

    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        print("ffmpeg failed:", e)
        return False

    # copy mtime/ctime from src to dst
    try:
        st = src.stat()
        mtime = datetime.fromtimestamp(st.st_mtime)
        apply_system_time(dst, mtime, dry_run=dry_run)
    except Exception:
        pass

    # move original if requested
    if move_original_to:
        move_original_to.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(move_original_to / src.name))

    return True
