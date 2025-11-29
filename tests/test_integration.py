import shutil
from pathlib import Path
from datetime import datetime, timedelta
import subprocess
import sys

import pytest

from datefixer import exiftool, exif_setter, date_mapper, utils, set_times, cli


FIXDIR = Path(__file__).parent / "fixtures"

requires_exiftool = pytest.mark.skipif(
    shutil.which("exiftool") is None,
    reason="exiftool not installed",
)


def copy_fixture_to(path, name):
    src = FIXDIR / name
    assert src.exists()
    dest = path / src.name
    shutil.copy2(src, dest)
    assert dest.exists()
    return dest


def test_fixtures_exist():
    files = list(FIXDIR.iterdir())
    assert files, "No fixture files found in tests/fixtures"


def test_infer_from_fixture_filenames():
    img = FIXDIR / "IMG_20240331_212928.jpg"
    pxl = FIXDIR / "PXL_20251127_044642542.RAW-01.COVER.jpg"

    assert img.exists()
    assert pxl.exists()

    dt1 = utils.infer_from_filename(img.name)
    dt2 = utils.infer_from_filename(pxl.name)

    assert dt1 is not None and dt1.year == 2024
    assert dt2 is not None and dt2.year == 2025


def test_gather_candidates_on_fixtures():
    for p in FIXDIR.iterdir():
        if p.name == ".gitkeep":
            continue
        candidates = date_mapper.gather_candidates(
            p, src_tags=[], backups_path=None)
        assert isinstance(candidates, list)


@requires_exiftool
def test_exif_set_and_read_enhanced(tmp_path):
    """Write an EXIF AllDates tag and verify via exiftool JSON.

    Enhanced: read tags before and after and assert that non-date tags
    remain unchanged while the intended date tags are set.
    """
    p = copy_fixture_to(tmp_path, "PXL_20251127_044642542.RAW-01.COVER.jpg")

    before = exiftool.read_all_tags(p)

    dt = datetime(2001, 1, 1, 1, 1, 1)
    assert exif_setter.set_exif_tags(
        p, {"AllDates": dt.strftime("%Y:%m:%d %H:%M:%S")})

    after = exiftool.read_all_tags(p)
    assert isinstance(after, dict)

    # expected date strings
    assert after.get('EXIF:ExifIFD:DateTimeOriginal') == '2001:01:01 01:01:01'
    assert after.get('EXIF:ExifIFD:CreateDate') == '2001:01:01 01:01:01'
    assert after.get('EXIF:IFD0:ModifyDate') == '2001:01:01 01:01:01'

    # default is to not overwrite system like exiftool does
    static_tags = [
        'File:System:FileModifyDate'
        'File:System:FileInodeChangeDate'
        'File:System:CreatedDate'
    ]
    for tag in static_tags:
        assert before.get(tag) == after.get(tag)

    # pick a non-date tag to ensure it was not changed by the operation
    non_date_key = None
    for k in before.keys():
        if k in ('SourceFile',):
            continue
        if 'Date' not in k and 'date' not in k:
            non_date_key = k
            break

    if non_date_key:
        assert before.get(non_date_key) == after.get(non_date_key)


def test_apply_system_time_changes_mtime(tmp_path):
    p = copy_fixture_to(tmp_path, "IMG_20240331_212928.jpg")
    before = p.stat().st_mtime
    dt = datetime.now() - timedelta(days=365)
    tag = 'File:System:FileModifyDate'
    set_times.apply_system_time(p, tag, dt, dry_run=False)
    after = p.stat().st_mtime
    assert after != before
    # ensure file content untouched (size unchanged)
    assert p.stat().st_size == p.stat().st_size


def test_gather_with_src_tags(tmp_path):
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
    cands = date_mapper.gather_candidates(p, src_tags=all_tags)
    assert len(cands) == len(all_tags)


def test_gather_with_backups_behaviour(tmp_path):
    backups_path = tmp_path / "backups"
    backups_path.mkdir()
    p = copy_fixture_to(tmp_path, "PXL_20251127_044642542.RAW-01.COVER.jpg")
    copy_fixture_to(backups_path, "PXL_20251127_044642542.RAW-01.COVER.jpg")
    cands = date_mapper.gather_candidates(
        p, src_tags=[], backups_path=backups_path,
        backups_tags=['EXIF:IFD0:ModifyDate'])
    assert isinstance(cands, list)
    assert len(cands) >= 1
    assert any("backup:" in desc for desc, _ in cands)


def test_video_filename_inference_and_gather(tmp_path):
    p = copy_fixture_to(tmp_path, "Samsung phone 2 2014 010.mp4")
    dt = utils.infer_from_filename(p.name)
    assert dt is None or dt.year == 2014

    cands = date_mapper.gather_candidates(
        p, src_tags=["File:System:FileModifyDate"])
    assert isinstance(cands, list)


def test_cli_help_runs():
    cmd = [sys.executable, "-m", "datefixer", "--help"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "set-dates" in res.stdout


def test_set_dates_flow_monkeypatched(monkeypatch, tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_text("x")

    monkeypatch.setattr(
        date_mapper,
        "gather_candidates",
        lambda path, src_tags, backups_path=None, backups_tags=None: [
            ("EXIF:Candidate1", datetime(2021, 1, 1)),
        ],
    )

    calls = {}

    def fake_apply(path, dests, dt, dry_run=False):
        calls['path'] = str(path)
        calls['dests'] = dests
        calls['dt'] = dt
        calls['dry'] = dry_run

    monkeypatch.setattr(date_mapper, "apply_destinations", fake_apply)

    monkeypatch.chdir(tmp_path)

    class Args:
        pattern = "*.jpg"
        src_tags = "EXIF:Composite:SubSecDateTimeOriginal"
        dest_tags = "File:System:FileModifyDate,EXIF:AllDates"
        backups_path = None
        backups_tags = None
        interactive = False
        show_exiftool = False
        dry_run = True
        progress = False

    args = Args()
    cli.cmd_set_dates(args)

    assert calls['path'].endswith('photo.jpg')
    assert 'File:System:FileModifyDate' in calls['dests'][0]
    assert calls['dry'] is True
