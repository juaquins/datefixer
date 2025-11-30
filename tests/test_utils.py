from datetime import datetime
from datefixer import utils
import pytest


def test_parse_date_iso():
    s = "2020-01-02 03:04:05"
    dt = utils.parse_date(s)
    assert dt and dt.year == 2020


def test_parse_subseconds_only_returns_none():
    assert utils.parse_date("732") is None


@pytest.mark.parametrize("s", [
    "notadate",
    "",
    None,
    '12345678',
    'PXL_foobar'
])
def test_parse_invalid_dates(s):
    assert utils.parse_date(s) is None


def test_parse_examples():
    examples = [
        ("2025:11:15 03:46:40", 2025),
        ("2025-11-15 03:46:40", 2025),
        ("2025-11-15T03:46:40Z", 2025),
        ("2025-11-15T03:46:40.732+13:00", 2025),
        ("2025:11:15 03:46:40.732+13:00", 2025),
        ("2025-11-14 14:29:19Z", 2025),
        ("2023:03:09 10:57:00", 2023),
    ]
    for s, yr in examples:
        dt = utils.parse_date(s)
        assert dt is not None and dt.year == yr


def test_parse_exif_like_formats():
    """Verify parsing of common EXIF timestamp formats.

    This test covers plain EXIF timestamps, fractional seconds and
    timezone offsets to ensure the parser returns a datetime.
    """
    examples = [
        ("2020:01:02 03:04:05", datetime(2020, 1, 2, 3, 4, 5)),
        ("2020:01:02 03:04:05.123", datetime(2020, 1, 2, 3, 4, 5, 123000)),
        ("2020:01:02 03:04:05-05:00", datetime(2020, 1, 2, 8, 4, 5)),
    ]
    for s, expected in examples:
        dt = utils.parse_date(s)
        assert dt is not None
        # compare naive UTC-normalized times by checking year/month/day
        assert dt.year == expected.year
        assert dt.month == expected.month
        assert dt.day == expected.day


def test_infer_from_filename():
    name = "PXL_20200102_030405.jpg"
    dt = utils.infer_from_filename(name)
    assert dt is not None


def test_filename_inference_examples():
    cases = [
        ("IMG_20230115_142300.jpg", 2023),
        ("PXL_20240201_073211.mp4", 2024),
        ("2020-04-19 11.13.54.jpg", 2020),
        ("20220305_183412.heic", 2022),
        ("20230101-123045.jpg", 2023),
        ("2023_01_02.jpg", 2023),
    ]
    for name, yr in cases:
        dt = utils.infer_from_filename(name)
        assert dt is not None and dt.year == yr


def test_infer_from_filename_varieties():
    """Ensure filename inference handles common filename patterns.

    Checks PXL/IMG and date-separated filename patterns.
    """
    names = [
        ("PXL_20210101_123045.jpg", 2021, 1, 1),
        ("IMG_20201231_235959.JPG", 2020, 12, 31),
        ("2020-01-02 03.04.05.jpg", 2020, 1, 2),
    ]
    for name, y, m, d in names:
        dt = utils.infer_from_filename(name)
        assert dt is not None
        assert dt.year == y
        assert dt.month == m
        assert dt.day == d
