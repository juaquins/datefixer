from datetime import datetime
from datefixer import exiftool


def test_earliest_time_from_exiftool_monkeypatched(monkeypatch):
    """Validate earliest-time extraction when exiftool returns mixed values.

    The sample contains naive timestamps, fractional-second strings and
    an offset-aware Composite field. The helper should normalize and
    return a datetime representing the earliest moment.
    """
    sample = {
        "SourceFile": "/tmp/photo.jpg",
        "EXIF:DateTimeOriginal": "2021:02:03 04:05:06",
        "EXIF:SubSecDateTimeOriginal": "2021:02:03 04:05:06.500",
        "Composite:SubSecDateTimeOriginal": "2021:02:03 04:05:06.500-05:00",
    }

    monkeypatch.setattr(exiftool, "has_exiftool", lambda: True)
    monkeypatch.setattr(exiftool, "read_all_tags", lambda p: sample)

    dt = exiftool.earliest_time_from_exiftool("/tmp/photo.jpg")
    assert isinstance(dt, datetime)
    # earliest should be 2021-02-03 04:05:06 (naive) or equivalent
    assert dt.year == 2021
    assert dt.month == 2
    assert dt.day == 3
