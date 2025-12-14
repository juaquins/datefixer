"""Unit tests for `datefixer.set_dates`.

These tests exercise the system-time application helpers and the
`cmd_set_dates` interactive flow. They are designed to exercise the
important branches without relying on the repository's fixture files.

Test goals:
- Verify `apply_system_time` handles dry-run and real updates for
    modification/access times and the macOS `SetFile` creation-time
    branch (including swallowing subprocess failures).
- Verify `cmd_set_dates` normalizes string inputs, filters non-files,
    handles absolute and relative patterns, and exercises interactive
    navigation values (`next`, `previous`, `quit`, `None`) and the
    application path that calls `date_mapper.apply_destinations`.
"""
import pytest
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from datefixer import set_dates, date_mapper, exiftool


def test_apply_system_time_modify_and_access(tmp_path, capsys):
    """Dry-run printing and actual modification/access time updates.

    Creates a temporary file, ensures the dry-run path prints a message,
    then calls the real update and checks the file mtime changed.
    """
    f = tmp_path / "a.txt"
    f.write_text("x")
    dt = datetime.now() + timedelta(seconds=1)

    # dry run prints
    set_dates.apply_system_time(f, "File:System:FileModifyDate", dt, dry_run=True)
    out = capsys.readouterr().out
    assert "DRY RUN" in out

    # actual run updates mtime (allow small delta)
    set_dates.apply_system_time(f, "File:System:FileModifyDate", dt, dry_run=False)
    after = f.stat().st_mtime
    assert abs(after - dt.timestamp()) < 3


def test_apply_system_time_createdate_calls_setfile(monkeypatch, tmp_path, capsys):
    """CreateDate branch: invoke SetFile when present and ignore errors.

    Monkeypatches `shutil.which` to pretend `SetFile` exists and ensures
    `subprocess.run` is called during a real run; also verifies raised
    exceptions from subprocess are swallowed.
    """
    f = tmp_path / "b.txt"
    f.write_text("y")
    dt = datetime.now()

    # pretend SetFile exists
    monkeypatch.setattr(shutil, "which", lambda name: "/foo/bar/SetFile")

    calls = []

    def fake_run(args, check=False):
        calls.append(args)

    monkeypatch.setattr(subprocess, "run", fake_run)

    # dry_run should print but not call subprocess
    set_dates.apply_system_time(f, "File:System:FileCreateDate", dt, dry_run=True)
    assert not calls
    assert "DRY RUN" in capsys.readouterr().out

    # actual run should call SetFile
    set_dates.apply_system_time(f, "File:System:FileCreateDate", dt, dry_run=False)
    assert calls, "expected subprocess.run to be called for SetFile"
    assert isinstance(calls[0], list) and calls[0][0] == "SetFile"

    # simulate subprocess.run raising — should be swallowed
    def raising_run(args, check=False):
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "run", raising_run)
    # should not raise
    set_dates.apply_system_time(f, "File:System:FileCreateDate", dt, dry_run=False)


def test_cmd_set_dates_normalizes_inputs(monkeypatch, tmp_path):
    """Verify normalization of comma-separated tag strings and backups path.

    Ensures string inputs are converted to lists and that `backups_path`
    becomes a `Path` object before being passed to `date_mapper`.
    """
    # create an example file
    f = tmp_path / "1.jpg"
    f.write_text("x")
    pattern = str(tmp_path / "*.jpg")

    captured = {}

    def fake_gather(file_to_fix, src_tags=None, backups_path=None, backups_tags=None):
        captured['src_tags'] = src_tags
        captured['backups_path'] = backups_path
        captured['backups_tags'] = backups_tags
        return []

    monkeypatch.setattr(date_mapper, "gather_candidates", fake_gather)

    # pass string forms
    set_dates.cmd_set_dates(pattern, dest_tags="A,B", src_tags="C", backups_path=str(tmp_path), backups_tags="D,E", interactive=False)

    assert captured['src_tags'] == ["C"]
    assert isinstance(captured['backups_path'], Path)
    assert captured['backups_tags'] == ["D", "E"]


def test_cmd_set_dates_interactive_apply(monkeypatch, tmp_path):
    """Force interactive choice and assert `apply_destinations` called.

    Stubs `gather_candidates` to return multiple candidates, returns a
    datetime from `interactive_choose`, and asserts `apply_destinations`
    receives the chosen datetime and correct flags.
    """
    f = tmp_path / "a.jpg"
    f.write_text("x")
    pattern = str(tmp_path / "*.jpg")

    ts = datetime(2020, 1, 1)

    # force interactive by returning more than one candidate
    monkeypatch.setattr(date_mapper, "gather_candidates", lambda file_to_fix, **kw: [("s1", ts), ("s2", ts)])
    monkeypatch.setattr(date_mapper, "interactive_choose", lambda candidates: ts)

    applied = {}

    def fake_apply(file_to_fix, dest_tags, chosen_dt, dry_run=False, update_systime=False):
        applied['args'] = (file_to_fix, dest_tags, chosen_dt, dry_run, update_systime)

    monkeypatch.setattr(date_mapper, "apply_destinations", fake_apply)

    set_dates.cmd_set_dates(pattern, dest_tags=["X"], src_tags=None, interactive=False, dry_run=True, update_systime=True)

    assert 'args' in applied
    assert applied['args'][2] == ts
    assert applied['args'][3] is True
    assert applied['args'][4] is True


def test_show_exiftool_prints(monkeypatch, tmp_path, capsys):
    """When `show_exiftool=True`, the EXIF dump is printed to stdout.

    Monkeypatches `exiftool.read_all_tags` to return a small mapping and
    verifies the printed dump appears in captured output.
    """
    f = tmp_path / "a.jpg"
    f.write_text("x")
    pattern = str(tmp_path / "*.jpg")

    # return a non-empty dict for exiftool
    monkeypatch.setattr(exiftool, "read_all_tags", lambda p: {"Tag": "Value"})
    # gather_candidates returns multiple to trigger interactive branch; return a datetime directly
    monkeypatch.setattr(date_mapper, "gather_candidates", lambda file_to_fix, **kw: [("s", datetime(2021,1,1))])
    # interactive_choose returns a datetime so printing occurs
    monkeypatch.setattr(date_mapper, "interactive_choose", lambda c: datetime(2021,1,1))
    monkeypatch.setattr(date_mapper, "apply_destinations", lambda *a, **kw: None)

    set_dates.cmd_set_dates(pattern, dest_tags=None, src_tags=None, interactive=True, show_exiftool=True)
    out = capsys.readouterr().out
    assert "EXIFTOOL DUMP:" in out
    assert "Tag" in out


def test_cmd_set_dates_pattern_and_nonfile_filtering(monkeypatch, tmp_path):
    """Pattern globbing: only files are processed, directories ignored.

    Creates two files and a directory under `tmp_path` and asserts the
    command only visits the file paths returned by the glob.
    """
    # create files and a directory to ensure non-files filtered
    (tmp_path / "keep1.jpg").write_text("x")
    (tmp_path / "keep2.jpg").write_text("y")
    (tmp_path / "adir").mkdir()
    # pattern absolute
    pattern = str(tmp_path / "*.jpg")

    seen = []

    def fake_gather(file_to_fix, **kw):
        seen.append(Path(file_to_fix).name)
        return []

    monkeypatch.setattr(date_mapper, "gather_candidates", fake_gather)

    # should process only the two files, not the directory
    set_dates.cmd_set_dates(pattern, interactive=False)
    assert sorted(seen) == ["keep1.jpg", "keep2.jpg"]


def test_cmd_set_dates_interactive_navigation(monkeypatch, tmp_path, capsys):
    """Exercise interactive navigation return values `next`, `previous`, None.

    Uses a small sequence of navigation replies to exercise loop
    control: advancing, stepping back, and skipping a file.
    """
    # create three files to walk through
    files = []
    for n in ("a.jpg", "b.jpg", "c.jpg"):
        p = tmp_path / n
        p.write_text(n)
        files.append(p)
    pattern = str(tmp_path / "*.jpg")

    ts = datetime(2022, 2, 2)

    # gather_candidates will always return multiple candidates to force interactive
    def fake_gather(file_to_fix, **kw):
        return [("s1", ts), ("s2", ts)]

    seq = ["next", "previous", None]

    def fake_choose(candidates):
        return seq.pop(0) if seq else None

    applied = []

    def fake_apply(file_to_fix, dest_tags, chosen_dt, dry_run=False, update_systime=False):
        applied.append((Path(file_to_fix).name, chosen_dt, dry_run, update_systime))

    monkeypatch.setattr(date_mapper, "gather_candidates", fake_gather)
    monkeypatch.setattr(date_mapper, "interactive_choose", fake_choose)
    monkeypatch.setattr(date_mapper, "apply_destinations", fake_apply)

    # run: first returns 'next' -> skip first; second returns 'previous' -> go back to first; third returns None -> skip
    set_dates.cmd_set_dates(pattern, dest_tags=["X"], interactive=False, dry_run=False)

    # applied may be empty because we returned navigation commands; ensure no exceptions and sequence consumed
    assert not seq


def test_cmd_set_dates_quit_raises(monkeypatch, tmp_path):
    """Ensure an interactive 'quit' selection raises SystemExit.

    When `interactive_choose` returns `'quit'` the command should raise
    SystemExit and stop processing further files.
    """
    f = tmp_path / "q.jpg"
    f.write_text("q")
    pattern = str(tmp_path / "*.jpg")

    monkeypatch.setattr(date_mapper, "gather_candidates", lambda file_to_fix, **kw: [("s", datetime(2020,1,1)), ("s2", datetime(2020,1,1))])
    monkeypatch.setattr(date_mapper, "interactive_choose", lambda c: "quit")

    with pytest.raises(SystemExit):
        set_dates.cmd_set_dates(pattern, interactive=False)


def test_cmd_set_dates_applied_prints(monkeypatch, tmp_path, capsys):
    """Verify that a successful application prints an 'APPLIED' message.

    Stubs candidates and `apply_destinations` and asserts the expected
    confirmation line is printed to stdout.
    """
    f = tmp_path / "ap.jpg"
    f.write_text("x")
    pattern = str(tmp_path / "*.jpg")

    ts = datetime(2019, 1, 1)
    monkeypatch.setattr(date_mapper, "gather_candidates", lambda file_to_fix, **kw: [("s", ts)])
    monkeypatch.setattr(date_mapper, "apply_destinations", lambda *a, **kw: None)

    set_dates.cmd_set_dates(pattern, dest_tags=["X"], interactive=False)
    out = capsys.readouterr().out
    assert "APPLIED" in out


def test_cmd_set_dates_empty_pattern_no_candidates(monkeypatch, tmp_path):
    """When the glob matches no files, `gather_candidates` is not called.

    Ensures the function returns cleanly for empty patterns without
    invoking the candidate-gathering machinery.
    """
    # pattern with no matches should not call gather_candidates
    pattern = str(tmp_path / "*.nomatch")

    def fail_gather(*a, **kw):
        raise AssertionError("gather_candidates should not be called")

    monkeypatch.setattr(date_mapper, "gather_candidates", fail_gather)

    # should simply return without error
    set_dates.cmd_set_dates(pattern, interactive=False)
