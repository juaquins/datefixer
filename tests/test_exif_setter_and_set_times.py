from datetime import datetime
from datefixer import exif_setter, set_times
import subprocess


def test_set_exif_tags_dry_run(monkeypatch, tmp_path, capsys):
    """Dry-run calling of EXIF setter prints the expected command.

    This test verifies that when ``dry_run=True`` the function prints the
    would-be exiftool invocation and does not execute ``subprocess.run``.
    """
    p = tmp_path / "a.jpg"
    p.write_text("x")

    monkeypatch.setattr(exif_setter, "has_exiftool", lambda: True)

    # dry-run should print and return True without calling subprocess
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
    """Dry-run applying system time prints SetFile invocation when present.

    The test simulates macOS's SetFile being present and ensures the
    function prints the SetFile command rather than executing it when
    ``dry_run=True``.
    """
    p = tmp_path / "b.jpg"
    p.write_text("x")

    dt = datetime(2022, 3, 4, 5, 6, 7)

    # pretend SetFile exists
    monkeypatch.setattr(set_times, "has_setfile", lambda: True)

    # Should not raise; dry-run avoids actual os.utime
    tag = 'File:System:CreatedDate'
    set_times.apply_system_time(p, tag, dt, dry_run=True)
    out = capsys.readouterr().out
    assert "DRY RUN" in out
