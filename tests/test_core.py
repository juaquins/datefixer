from datetime import datetime
from pathlib import Path
import subprocess
import pytest
import sys
from datefixer import date_mapper, exiftool, exif_setter, set_times


def test_gather_candidates_from_exif(monkeypatch, tmp_path):
    p = tmp_path / "IMG_20230101.jpg"
    p.write_text("x")

    monkeypatch.setattr(
        exiftool,
        "read_all_tags",
        lambda path: {
            "Composite:SubSecDateTimeOriginal": (
                "2025:11:15 03:46:40.732+13:00"
            )
        },
    )
    src_tags = ["Composite:SubSecDateTimeOriginal"]
    res = date_mapper.gather_candidates(p, src_tags)
    assert any(isinstance(dt, datetime) for _, dt in res)


def test_gather_candidates_with_backups(monkeypatch, tmp_path):
    main = tmp_path / "photo.jpg"
    main.write_text("x")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    b = backup_dir / "photo.jpg"
    b.write_text("y")

    monkeypatch.setattr(
        exiftool,
        "earliest_time_from_exiftool",
        lambda path: datetime(2020, 1, 2, 3, 4, 5),
    )

    res = date_mapper.gather_candidates(
        main, ["File:System:FileModifyDate"], backups_path=backup_dir
    )
    assert any("backup:" in desc for desc, _ in res)


def test_apply_destinations_writes_exif(monkeypatch, tmp_path):
    p = tmp_path / "a.jpg"
    p.write_text("x")

    called = {}

    def fake_set_exif_tags(path, tags, dry_run=False):
        called['tags'] = tags
        called['path'] = path
        called['dry'] = dry_run
        return True

    monkeypatch.setattr(exif_setter, "set_exif_tags", fake_set_exif_tags)

    date_mapper.apply_destinations(
        p, ["EXIF:AllDates"], datetime(2021, 1, 1), dry_run=True
    )
    assert called["dry"] is True
    assert "AllDates" in list(called["tags"].keys())[0]


def test_set_exif_tags_dry_run(monkeypatch, tmp_path, capsys):
    p = tmp_path / "a.jpg"
    p.write_text("x")

    monkeypatch.setattr(exif_setter, "has_exiftool", lambda: True)

    called = {}

    def fake_run(cmd, check=None):
        called['cmd'] = cmd

    monkeypatch.setattr(subprocess, "run", fake_run)

    res = exif_setter.set_exif_tags(
        p,
        {"AllDates": "2020:01:01 00:00:00"},
        dry_run=True,
    )
    captured = capsys.readouterr()
    assert res is True
    assert "DRY RUN" in captured.out
    assert 'cmd' not in called


def test_apply_system_time_dry_run_with_setfile(monkeypatch, tmp_path, capsys):
    p = tmp_path / "b.jpg"
    p.write_text("x")

    dt = datetime(2022, 3, 4, 5, 6, 7)

    monkeypatch.setattr(set_times, "has_setfile", lambda: True)

    tag = 'File:System:CreatedDate'
    set_times.apply_system_time(p, tag, dt, dry_run=True)
    out = capsys.readouterr().out
    assert "DRY RUN" in out


def test_earliest_time_from_exiftool_monkeypatched(monkeypatch):
    sample = {
        "SourceFile": "/tmp/photo.jpg",
        "EXIF:DateTimeOriginal": "2021:02:03 04:05:06",
        "EXIF:SubSecDateTimeOriginal": "2021:02:03 04:05:06.500",
        "Composite:SubSecDateTimeOriginal": "2021:02:03 04:05:06.500-05:00",
    }

    monkeypatch.setattr(exiftool, "has_exiftool", lambda: True)
    monkeypatch.setattr(exiftool, "read_all_tags", lambda p: sample)

    dt = exiftool.earliest_time_from_exiftool(Path("/tmp/photo.jpg"))
    assert isinstance(dt, datetime)
    assert dt.year == 2021
    assert dt.month == 2
    assert dt.day == 3
