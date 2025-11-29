"""Helpers to call exiftool and parse its JSON output.

This module provides a small wrapper around the external ``exiftool``
binary. Reading functions return plain Python mappings (dictionaries)
or ``None`` so callers can gracefully fall back to filesystem-based
timestamps when exiftool is not available or fails.
"""
import json
import shutil
import subprocess
from typing import Dict
from pathlib import Path
from .utils import parse_date
from datetime import datetime, timezone


def has_exiftool():
    """Return ``True`` when the ``exiftool`` binary is found on PATH."""
    return shutil.which("exiftool") is not None


def read_all_tags(path: Path):
    """Return exiftool JSON mapping for ``path``.

    The function runs ``exiftool -time:all -a -G0:1 -s -j`` to obtain
    JSON output. If exiftool is not available or fails, an empty mapping
    is returned.

    Args:
        path: Path to the file to query.

    Returns:
        A dict with exiftool fields, or an empty dict on error.
    """
    if not has_exiftool():
        return {}
    try:
        r = subprocess.run(
            ["exiftool", "-time:all", "-a", "-G0:1", "-s", "-j", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
        )
        data = json.loads(r.stdout)
        return data[0] if data else {}
    except Exception:
        # If exiftool fails for any reason, return an empty mapping so callers
        # can fall back to filesystem-based timestamps.
        return {}


def all_times_from_exiftool(path: Path) -> Dict[str, datetime]:
    """Return all parsed datetimes found in exiftool output.

    The function parses all string values returned by ``read_all_tags`` and
    attempts to parse datetimes using :func:`datefixer.utils.parse_date`.
    Parsed datetimes are normalized to UTC-aware datetimes to avoid mixing
    naive and aware values.

    Args:
        path: Path to the file to inspect.

    Returns:
        A dict of tag name to timezone-aware :class:`datetime.datetime` in UTC or ``[]`` if
        no parsable times are found.
    """
    all_tags = read_all_tags(path)
    if not all_tags:
        return {}
    dt_tags = {}
    for k, v in all_tags.items():
        dt = parse_date(v)
        if dt and isinstance(dt, datetime):
            # Normalize to timezone-aware UTC so comparisons work
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            dt_tags[k] = dt
    return dt_tags


def earliest_time_from_exiftool(path: Path):
    """Return the earliest parsed datetime found in exiftool output.

    The function parses all string values returned by ``read_all_tags`` and
    attempts to parse datetimes using :func:`datefixer.utils.parse_date`.
    Parsed datetimes are normalized to UTC-aware datetimes to avoid mixing
    naive and aware values.

    Args:
        path: Path to the file to inspect.

    Returns:
        A timezone-aware :class:`datetime.datetime` in UTC or ``None`` if
        no parsable times are found.
    """
    exif_dates = all_times_from_exiftool(path).values()
    # Use timestamp-based min to avoid any remaining comparison issues
    return min(exif_dates, key=lambda d: d.timestamp())
