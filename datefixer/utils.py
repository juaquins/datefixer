"""Utility helpers for parsing dates and inferring dates from filenames.

This module centralizes parsing logic so tests and other modules can
re-use common heuristics for EXIF-style timestamps and filename-based
timestamps. The functions aim to be robust and fall back to
``dateutil.parser`` for tricky inputs.
"""

from datetime import datetime
import re
from dateutil import parser as dparser

EXPLICIT_FORMATS = [
    "%Y:%m:%d",
    "%Y:%m:%d %H:%M:%S",
    "%Y:%m:%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y:%m:%d %H:%M:%S%z",
    "%Y:%m:%d %H:%M:%S.%f%z",
]

FILENAME_PATTERNS = [
    (r"PXL_(\d{8}_\d{6})", "%Y%m%d_%H%M%S"),
    (r"PXL_(\d{8}_\d{6}\d{1,3})", "%Y%m%d_%H%M%S%f"),
    (r"IMG_(\d{8}_\d{6})", "%Y%m%d_%H%M%S"),
    (r"(\d{8})_(\d{6})", "%Y%m%d_%H%M%S"),
    (r"(\d{8})-(\d{6})", "%Y%m%d-%H%M%S"),
    (r"(\d{8})", "%Y%m%d"),
    (r"(\d{4}-\d{2}-\d{2} \d{2}\.\d{2}\.\d{2})", "%Y-%m-%d %H.%M.%S"),
    (r"(\d{8})_(\d{6})", "%Y%m%d_%H%M%S"),
    (r"(\d{4})_(\d{2})_(\d{2})", "%Y_%m_%d"),
]


def parse_date(s: str) -> datetime | None:
    """Try to parse many EXIF and filename timestamp formats.

    Uses explicit strptime formats for speed/accuracy, then falls back to
    dateutil.parser.parse which handles most variations and timezones.
    Returns a timezone-aware datetime when offset present, otherwise naive.
    """
    # Fast path: None or non-string inputs
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    # ignore small numeric-only values (subseconds)
    if re.fullmatch(r"\d{1,6}", s):
        return None

    # common cleanup
    # replace commas
    s2 = s.replace(",", " ")

    # Try explicit formats
    for fmt in EXPLICIT_FORMATS:
        try:
            # Python %z supports offsets like +HHMM or +HH:MM
            dt = datetime.strptime(s2, fmt)
            return dt
        except Exception:
            pass

    # Try a few heuristics for EXIF-like 'YYYY:MM:DD HH:MM:SS(.sss)(±HH:MM)'
    m = re.match(r"(\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2})(\.?\d+)?(.*)$", s2)
    if m:
        base = m.group(1)
        frac = m.group(2) or ""
        rest = m.group(3) or ""
        candidate = base + (frac if frac else "") + rest
        try:
            return dparser.parse(candidate)
        except Exception:
            pass

    # Final fallback: dateutil which handles many messy cases, including
    # timezone offsets and fuzzy parsing. This is slower but very robust.
    try:
        dt = dparser.parse(s2)
        return dt
    except Exception:
        pass

    return None


def infer_from_filename(name: str):
    if not name:
        return None
    for pat, fmt in FILENAME_PATTERNS:
        m = re.search(pat, name)
        if m:
            try:
                group = m.group(1)
                # for patterns with two groups (date+time) join them
                if m.lastindex and m.lastindex > 1:
                    group = "_".join(m.groups())
                return datetime.strptime(group, fmt)
            except Exception:
                continue
    # fallback: try dateutil on filename
    # strip extension
    base = re.sub(r"\.[^.]+$", "", name)
    try:
        return dparser.parse(base, fuzzy=True)
    except Exception:
        return None
