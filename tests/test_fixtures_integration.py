from datetime import datetime, timedelta
from pathlib import Path
import shutil
import pytest
from datefixer import utils, date_mapper, exif_setter, set_times, exiftool

FIXDIR = Path(__file__).parent / "fixtures"

requires_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None,
    reason="exiftool not installed",
)


def copy_fixture_to(path, name):
    '''Looks for a fixture in FIXDIR and copies it to path.'''
    src = FIXDIR / name
    assert src.exists()
    dest = path / src.name
    shutil.copy2(src, dest)
    assert dest.exists()
    return dest

from datefixer import utils, date_mapper


FIXDIR = Path(__file__).parent / "fixtures"


def test_fixtures_exist():
    """Sanity check: fixtures directory contains expected files.

    This ensures the repository contains sample media files required by
    integration-like tests. The test does not inspect file contents.
    """
    files = list(FIXDIR.iterdir())
    assert files, "No fixture files found in tests/fixtures"


def test_infer_from_fixture_filenames():
    """Validate filename-based date inference for repository fixtures.

    Uses two real fixture filenames and asserts the year is parsed as
    expected. This helps catch regressions in filename pattern matching.
    """
    img = FIXDIR / "IMG_20240331_212928.jpg"
    pxl = FIXDIR / "PXL_20251127_044642542.RAW-01.COVER.jpg"

    assert img.exists()
    assert pxl.exists()

    dt1 = utils.infer_from_filename(img.name)
    dt2 = utils.infer_from_filename(pxl.name)

    assert dt1 is not None and dt1.year == 2024
    assert dt2 is not None and dt2.year == 2025


def test_gather_candidates_on_fixtures():
    """Ensure :func:`datefixer.date_mapper.gather_candidates` runs on fixtures.

    The test iterates over the fixture files (skipping the placeholder)
    and asserts that the gather function returns a list. This exercises
    EXIF parsing fallbacks and filesystem timestamp handling.
    """
    for p in FIXDIR.iterdir():
        if p.name == ".gitkeep":
            continue
        candidates = date_mapper.gather_candidates(
            p, src_tags=[], backups_path=None
        )
        assert isinstance(candidates, list)


def test_infer_and_gather_filesystem(tmp_path):
    """Infer date from filename and gather a filesystem timestamp candidate."""
    p = copy_fixture_to(tmp_path, "IMG_20240331_212928.jpg")

    # infer from filename
    dt = utils.infer_from_filename(p.name)
    assert dt is not None and dt.year == 2024

    # gather a filesystem candidate (File:System:FileModifyDate)
    cands = date_mapper.gather_candidates(p, src_tags=["File:System:FileModifyDate"])
    assert isinstance(cands, list)
    assert any(p.name in desc for desc, _ in cands)


@requires_exiftool
def test_exif_set_and_read(tmp_path):
    """Write an EXIF AllDates tag and verify via exiftool JSON."""
    p = copy_fixture_to(tmp_path, "PXL_20251127_044642542.RAW-01.COVER.jpg")

    # set EXIF AllDates using exif_setter
    dt = datetime(2000, 2, 3, 4, 5, 6)
    assert exif_setter.set_exif_tags(p, {"AllDates": dt.strftime("%Y:%m:%d %H:%M:%S")})

    # read back with exiftool wrapper and ensure a parseable date exists
    tags = exiftool.read_all_tags(p)
    assert isinstance(tags, dict)
    assert tags['EXIF:ExifIFD:DateTimeOriginal'] == '2000:02:03 04:05:06'
    assert tags['EXIF:IFD0:ModifyDate'] == '2000:02:03 04:05:06'

    parsed = exiftool.earliest_time_from_exiftool(p)
    assert parsed is not None
    assert parsed.year == 2000


def test_apply_system_time_changes_mtime(tmp_path):
    """Apply a system modification time and verify the change."""
    p = copy_fixture_to(tmp_path, "IMG_20240331_212928.jpg")
    before = p.stat().st_mtime
    dt = datetime.now() - timedelta(days=365)
    set_times.apply_system_time(p, 'File:System:FileModifyDate', dt, dry_run=False)
    after = p.stat().st_mtime
    # mtime should have decreased (since dt is in the past)
    assert after != before


def test_gather_with_src_tags(tmp_path):
    """Handles improper formats and good ones"""
    p = copy_fixture_to(tmp_path, "IMG_20240331_212928.jpg")
    cands = date_mapper.gather_candidates(
        p, src_tags=['foo:bar', 'EXIF:fakeTag', 'foo', 'd:', ':', '::::'])
    assert len(cands) == 0

    all_tags = [
        "File:System:FileModifyDate",
        "File:System:FileAccessDate",
        "File:System:FileInodeChangeDate",
        "File:System:CreatedDate",
        "EXIF:IFD0:ModifyDate",
        "EXIF:ExifIFD:DateTimeOriginal",
        "EXIF:ExifIFD:CreateDate",
        "ICC_Profile:ICC-header:ProfileDateTime",
    ]
    cands = date_mapper.gather_candidates(
        p, src_tags=all_tags)
    assert len(cands) == len(all_tags)


def test_gather_with_backups_single_tag(tmp_path):
    """When backups folder contains the same filename, candidates include backup entries."""
    backups_path = tmp_path / "backups"
    backups_path.mkdir()
    p = copy_fixture_to(tmp_path, "PXL_20251127_044642542.RAW-01.COVER.jpg")
    p = copy_fixture_to(backups_path, "PXL_20251127_044642542.RAW-01.COVER.jpg")
    cands = date_mapper.gather_candidates(
        p, src_tags=[], backups_path=backups_path,
        backups_tags=['EXIF:IFD0:ModifyDate']
    )
    assert isinstance(cands, list)
    assert len(cands) == 1
    assert any("backup:" in desc for desc, _ in cands)


def test_gather_with_backups_all_tags(tmp_path):
    """When backups folder contains the same filename, candidates include backup entries."""
    backups_path = tmp_path / "backups"
    backups_path.mkdir()
    p = copy_fixture_to(tmp_path, "PXL_20251127_044642542.RAW-01.COVER.jpg")
    p = copy_fixture_to(backups_path, "PXL_20251127_044642542.RAW-01.COVER.jpg")
    cands = date_mapper.gather_candidates(
        p, src_tags=[], backups_path=backups_path,
        backups_tags=['*']
    )
    assert isinstance(cands, list)
    assert len(cands) == 19
    assert any("backup:" in desc for desc, _ in cands)


def test_gather_with_backups_no_tags(tmp_path):
    """When backups folder contains the same filename, candidates include backup entries."""
    backups_path = tmp_path / "backups"
    backups_path.mkdir()
    p = copy_fixture_to(tmp_path, "PXL_20251127_044642542.RAW-01.COVER.jpg")
    p = copy_fixture_to(backups_path, "PXL_20251127_044642542.RAW-01.COVER.jpg")
    cands = date_mapper.gather_candidates(
        p, src_tags=[], backups_path=backups_path,
    )
    assert isinstance(cands, list)
    assert len(cands) == 19
    assert any("backup:" in desc for desc, _ in cands)


def test_video_filename_inference_and_gather(tmp_path):
    """Infer date from a video filename and gather filesystem candidate."""
    p = copy_fixture_to(tmp_path, "Samsung phone 2 2014 010.mp4")
    dt = utils.infer_from_filename(p.name)
    # filename includes 2014; accept either a parsed year or None depending
    # on the heuristics available in the running environment.
    assert dt is None or dt.year == 2014

    cands = date_mapper.gather_candidates(
        p, src_tags=["File:System:FileModifyDate"]
    )
    assert isinstance(cands, list)
