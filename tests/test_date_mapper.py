from datefixer import date_mapper, exiftool, exif_setter
from datetime import datetime


def test_gather_candidates_from_exif(monkeypatch, tmp_path):
    p = tmp_path / "IMG_20230101.jpg"
    p.write_text("x")

    # mock exiftool.read_all_tags to return Composite tag
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
    # create main file and backup copy
    main = tmp_path / "photo.jpg"
    main.write_text("x")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    b = backup_dir / "photo.jpg"
    b.write_text("y")

    # mock exiftool.earliest_time_from_exiftool on backup
    monkeypatch.setattr(
        exiftool,
        "earliest_time_from_exiftool",
        lambda path: datetime(2020, 1, 2, 3, 4, 5),
    )

    res = date_mapper.gather_candidates(
        main, ["File:System:FileModifyDate"], backups_path=backup_dir
    )
    # should include backup candidate
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
