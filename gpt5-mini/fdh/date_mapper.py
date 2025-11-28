"""Gather candidate dates from EXIF, system, and reference backups.

Prompt interactively and apply to destinations.
"""
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional
from . import exiftool, set_times, exif_setter, utils
import glob


def system_tag_to_datetime(path: Path, tag: str) -> Optional[datetime]:
    st = path.stat()
    if tag.endswith("FileModifyDate"):
        return datetime.fromtimestamp(st.st_mtime)
    if tag.endswith("FileInodeChangeDate"):
        # platform dependent; use st_ctime as inode change time
        return datetime.fromtimestamp(st.st_ctime)
    if tag.endswith("FileCreateDate"):
        # macOS has st_birthtime; fallback to mtime
        try:
            return datetime.fromtimestamp(st.st_birthtime)
        except Exception:
            return datetime.fromtimestamp(st.st_mtime)
    return None


def gather_candidates(
    path: Path,
    src_tags: List[str],
    src_backups: Optional[Path] = None,
) -> List[Tuple[str, datetime]]:
    """Return list of (description, datetime) candidates for the file.

        src_tags are strings like:
            - `EXIF:Composite:SubSecDateTimeOriginal` (grouped tag as
                exiftool outputs with -G0:1)
            - `File:System:FileModifyDate` (filesystem times)
    """
    candidates: List[Tuple[str, datetime]] = []

    # read exiftool output once
    exif_data = exiftool.read_all_tags(path)

    # gather from requested src_tags
    for tag in src_tags:
        if tag.startswith("EXIF:") or (
            ":" in tag and not tag.startswith("File:System:")
        ):
            # Exif-like tag: try to directly lookup key in exif_data
            key = tag.split("EXIF:", 1)[-1]
            # exiftool keys include group like Composite:SubSecDateTimeOriginal
            val = exif_data.get(key)
            if not val:
                # try raw without group
                val = exif_data.get(key.split(":")[-1])
            if val:
                if isinstance(val, list):
                    for v in val:
                        dt = utils.parse_date(v)
                        if dt:
                            candidates.append((f"{tag}: {v}", dt))
                elif isinstance(val, str):
                    dt = utils.parse_date(val)
                    if dt:
                        candidates.append((f"{tag}: {val}", dt))
        elif tag.startswith("File:System:"):
            # system tag mapping
            sys_tag = tag.split("File:System:", 1)[-1]
            dt = system_tag_to_datetime(path, sys_tag)
            if dt:
                candidates.append((f"{tag} (filesystem)", dt))
        else:
            # fallback: try raw exif_data key
            val = exif_data.get(tag)
            if val:
                dt = utils.parse_date(val) if isinstance(val, str) else None
                if dt:
                    candidates.append((f"{tag}: {val}", dt))

    # gather from backups (reference folder) if provided
    if src_backups:
        # match filename in backups recursively
        name = path.name
        matches = glob.glob(
            str(Path(src_backups) / "**" / name), recursive=True
        )
        for m in matches:
            mpath = Path(m)
            # try exiftool earliest
            ed = exiftool.earliest_time_from_exiftool(mpath)
            if ed:
                candidates.append((f"backup:{mpath} (exif)", ed))
            # also include system times
            cts = system_tag_to_datetime(mpath, "FileCreateDate")
            if cts:
                candidates.append((f"backup:{mpath} (create)", cts))
            mts = system_tag_to_datetime(mpath, "FileModifyDate")
            if mts:
                candidates.append((f"backup:{mpath} (modify)", mts))

    # unique-ify by datetime string representation (keep first description)
    seen = {}
    out = []
    for desc, dt in candidates:
        key = dt.isoformat()
        if key not in seen:
            seen[key] = desc
            out.append((desc, dt))
    return out


def apply_destinations(
    path: Path, dests: List[str], dt: datetime, dry_run: bool = False
):
    """Apply chosen datetime to one or more destination tags.

    dests examples:
      - `File:System:FileModifyDate`
      - `EXIF:ExifIFD:DateTimeOriginal`
      - `EXIF:AllDates` (exiftool supports AllDates)
    """
    for d in dests:
        if d.startswith("File:System:"):
            # apply to filesystem
            set_times.apply_system_time(path, dt, dry_run=dry_run)
        elif d.startswith("EXIF:") or d.startswith("Exif:"):
            # write exif tag via exiftool; tag string is what exiftool expects
            tag_to_set = (
                d.split("EXIF:", 1)[-1] if d.startswith("EXIF:") else d
            )
            # exif_setter expects dict mapping tag->value
            dt_str = dt.strftime("%Y:%m:%d %H:%M:%S")
            exif_setter.set_exif_tags(
                path, {tag_to_set: dt_str}, dry_run=dry_run
            )
        else:
            # unknown destination: try exiftool tag directly
            dt_str = dt.strftime("%Y:%m:%d %H:%M:%S")
            exif_setter.set_exif_tags(path, {d: dt_str}, dry_run=dry_run)


def interactive_choose(
    candidates: List[Tuple[str, datetime]]
) -> Optional[datetime]:
    """Prompt user to choose one candidate or provide custom datetime.

    Returns chosen datetime or None to skip.
    """
    if not candidates:
        return None
    print("Multiple possible dates found:")
    for i, (desc, dt) in enumerate(candidates):
        print(f"{i}: {desc} -> {dt}")
    print("c: custom date, s: skip, q: quit")
    while True:
        ans = input("Choose index (default 0): ").strip().lower()
        if ans == "":
            return candidates[0][1]
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
        if ans.isdigit():
            idx = int(ans)
            if 0 <= idx < len(candidates):
                return candidates[idx][1]
        print("Invalid choice")
