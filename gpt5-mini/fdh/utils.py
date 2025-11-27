import re
from datetime import datetime, timezone

DATE_FORMATS = [
    "%Y:%m:%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
]

FILENAME_PATTERNS = [
    (r"PXL_(\d{8}_\d{6})", "%Y%m%d_%H%M%S"),
    (r"IMG_(\d{8})", "%Y%m%d"),
    (r"(\d{8})", "%Y%m%d"),
]


def parse_date(date_str):
    """Try several date formats and return a datetime or None."""
    if not date_str or not isinstance(date_str, str):
        return None
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Pixel-style strings sometimes appear with PXL_ prefix
            if date_str.startswith("PXL_"):
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    return None


def infer_from_filename(name: str):
    for pat, fmt in FILENAME_PATTERNS:
        m = re.search(pat, name)
        if m:
            try:
                return datetime.strptime(m.group(1), fmt)
            except Exception:
                continue
    return None
