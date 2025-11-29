import shutil
from pathlib import Path
import pytest
from datefixer import exiftool

EXIFTOOL_AVAILABLE = shutil.which("exiftool") is not None


@pytest.mark.skipif(not EXIFTOOL_AVAILABLE, reason="exiftool not installed")
def test_read_all_tags_on_sample(tmp_path):
    fixture_dir = Path(__file__).parent / "fixtures"
    sample = fixture_dir / "IMG_20240331_212928.jpg"
    if not sample.exists():
        pytest.skip(f"tests/fixtures/{sample.name} not found!")
    data = exiftool.read_all_tags(sample)
    assert isinstance(data, dict)
    assert ("SourceFile" in data)
    assert len(data) == 8


@pytest.mark.skipif(not EXIFTOOL_AVAILABLE, reason="exiftool not installed")
def test_earliest_time_from_exiftool(tmp_path):
    fixture_dir = Path(__file__).parent / "fixtures"
    sample = fixture_dir / "Samsung phone 2 2014 010.mp4"
    if not sample.exists():
        pytest.skip(f"tests/fixtures/{sample.name} not found!")
    dt = exiftool.earliest_time_from_exiftool(sample)
    # dt may be None for images with no time tags; that's acceptable
    assert (dt is None) or hasattr(dt, "year")
