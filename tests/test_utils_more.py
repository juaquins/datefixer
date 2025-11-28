from datefixer import utils
import pytest


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


def test_parse_subseconds_only_returns_none():
    assert utils.parse_date("732") is None


@pytest.mark.parametrize("s", ["notadate", "", None])
def test_parse_invalid(s):
    assert utils.parse_date(s) is None
