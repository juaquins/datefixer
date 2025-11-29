from datefixer import date_mapper, exiftool
from pathlib import Path


SAMPLE_EXIF = {
    "SourceFile": (
        "/Users/juaquin/SyncThing/Media/Camera/2025/"
        "sample1.jpg"
    ),
    "File:System:FileModifyDate": "2025:11:14 09:46:47-05:00",
    "File:System:FileAccessDate": "2025:11:27 13:13:51-05:00",
    "File:System:FileInodeChangeDate": "2025:11:25 02:41:51-05:00",
    "EXIF:IFD0:ModifyDate": "2025:11:15 03:46:40",
    "EXIF:ExifIFD:DateTimeOriginal": "2025:11:15 03:46:40",
    "EXIF:ExifIFD:CreateDate": "2025:11:15 03:46:40",
    "EXIF:ExifIFD:OffsetTime": "+13:00",
    "EXIF:ExifIFD:OffsetTimeOriginal": "+13:00",
    "EXIF:ExifIFD:OffsetTimeDigitized": "+13:00",
    "EXIF:ExifIFD:SubSecTime": 732,
    "EXIF:ExifIFD:SubSecTimeOriginal": 732,
    "EXIF:ExifIFD:SubSecTimeDigitized": 732,
    "EXIF:GPS:GPSTimeStamp": "14:29:19",
    "EXIF:GPS:GPSDateStamp": "2025:11:14",
    "ICC_Profile:ICC-header:ProfileDateTime": "2023:03:09 10:57:00",
    "Composite:SubSecCreateDate": "2025:11:15 03:46:40.732+13:00",
    "Composite:SubSecDateTimeOriginal": "2025:11:15 03:46:40.732+13:00",
    "Composite:SubSecModifyDate": "2025:11:15 03:46:40.732+13:00",
    "Composite:GPSDateTime": "2025:11:14 14:29:19Z",
}


def test_parse_composite_subsec_and_tz(monkeypatch, tmp_path):
    # create a fake file path
    sample_path = Path(SAMPLE_EXIF['SourceFile'])
    p = tmp_path / sample_path.name
    p.write_text("x")
    assert p.exists()

    monkeypatch.setattr(exiftool, "read_all_tags", lambda path: SAMPLE_EXIF)

    candidates = date_mapper.gather_candidates(
        p, src_tags=["Composite:SubSecDateTimeOriginal"]
    )
    assert candidates, "No candidates found from sample exif"
    _desc, dt = candidates[0]
    assert dt.year == 2025

    # fractional seconds preserved
    assert dt.microsecond != 0

    # timezone offset present in string should be parsed as aware datetime
    assert hasattr(dt, "tzinfo")
    assert dt.tzinfo is not None


def test_parse_gps_datetime(monkeypatch, tmp_path):
    p = tmp_path / "gps.jpg"
    p.write_text("y")
    monkeypatch.setattr(exiftool, "read_all_tags", lambda path: SAMPLE_EXIF)
    candidates = date_mapper.gather_candidates(
        p, src_tags=["Composite:GPSDateTime"]
    )
    assert any(
        "GPS" in desc or "GPSDateTime" in desc for desc, _ in candidates
    )
    # find the parsed GPS datetime
    gps_dt = None
    for desc, dt in candidates:
        if "GPS" in desc:
            gps_dt = dt
            break
    assert gps_dt is not None and gps_dt.year == 2025
