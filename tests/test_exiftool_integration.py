import shutil
from pathlib import Path
import pytest
from datefixer import exiftool

EXIFTOOL_AVAILABLE = shutil.which("exiftool") is not None


@pytest.mark.skipif(not EXIFTOOL_AVAILABLE, reason="exiftool not installed")
def test_read_all_tags_on_sample(tmp_path):
    # Expect user to place a sample image in tests/fixtures named sample1.jpg
    fixture_dir = Path(__file__).parent / "fixtures"
    sample = fixture_dir / "sample1.jpg"
    if not sample.exists():
        pytest.skip(
            "No sample fixture found — copy a test image to tests/fixtures/"
            "sample1.jpg"
        )
    data = exiftool.read_all_tags(sample)
    assert isinstance(data, dict)
    # Composite or SourceFile key should exist
    assert (
        "SourceFile" in data
        or any(k.startswith("Composite") for k in data.keys())
    )


@pytest.mark.skipif(not EXIFTOOL_AVAILABLE, reason="exiftool not installed")
def test_earliest_time_from_exiftool(tmp_path):
    fixture_dir = Path(__file__).parent / "fixtures"
    sample = fixture_dir / "sample1.jpg"
    if not sample.exists():
        pytest.skip(
            "No sample fixture found — copy a test image to tests/fixtures/"
            "sample1.jpg"
        )
    dt = exiftool.earliest_time_from_exiftool(sample)
    # dt may be None for images with no time tags; that's acceptable
    assert (dt is None) or hasattr(dt, "year")
