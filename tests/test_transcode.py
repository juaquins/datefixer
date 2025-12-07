from pathlib import Path
import pytest
import shutil
from datefixer import (
    transcode as transcode_mod
)


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


def test_video_transcode_dry_run(tmp_path):
    temp_file = copy_fixture_to(tmp_path, "Samsung phone 2 2014 010.mp4")
    assert temp_file.exists() and temp_file.is_file()

    output_file = Path(temp_file.parent / f"{temp_file.stem}.reduced.mp4")
    assert not output_file.exists()

    success = transcode_mod.transcode_video(
        src=temp_file,
        dst=output_file,
        crf=32,
        dry_run=True
    )
    assert success
    assert not output_file.exists()
    # didn't move it so it should still be there
    assert temp_file.exists()


def test_video_transcode(tmp_path):
    temp_file = copy_fixture_to(tmp_path, "Samsung phone 2 2014 010.mp4")
    assert temp_file.exists() and temp_file.is_file()

    output_file = Path(temp_file.parent / f"{temp_file.stem}.reduced.mp4")
    assert not output_file.exists()

    success = transcode_mod.transcode_video(
        src=temp_file,
        dst=output_file,
        crf=32,
    )
    assert success
    assert output_file.exists() and output_file.is_file()
    # didn't move it so it should still be there
    assert temp_file.exists()

    # output file should be smaller than input
    assert output_file.stat().st_size < temp_file.stat().st_size


def test_video_transcode_with_move(tmp_path):
    temp_file = copy_fixture_to(tmp_path, "Samsung phone 2 2014 010.mp4")
    assert temp_file.exists() and temp_file.is_file()

    output_file = Path(temp_file.parent / f"{temp_file.stem}.reduced.mp4")
    assert not output_file.exists()

    originals_dir = temp_file.parent / 'originals'
    success = transcode_mod.transcode_video(
        src=temp_file,
        dst=output_file,
        crf=32,
        move_original_to=originals_dir
    )
    assert success
    assert output_file.exists() and output_file.is_file()
    assert not temp_file.exists()

    moved_temp_file = originals_dir / temp_file.name
    assert moved_temp_file.exists() and output_file.is_file()
    # output file should be smaller than input
    assert output_file.stat().st_size < moved_temp_file.stat().st_size
