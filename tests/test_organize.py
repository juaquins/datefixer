"""Tests for `datefixer.organize`.

These tests aim to cover the main branches of `organize_by_year`:

- dry-run behavior (no actual file operations, returns planned moves)
- actual move (files are moved into year folders)
- skipping non-files (directories matching pattern are ignored)
- grouping multiple files into the correct year folders

The implementation uses monkeypatching of the current working directory
and a small fake `stat` implementation to control the `st_birthtime`
value returned for files. This allows deterministic testing without
depending on platform-specific filesystem birthtime behavior.
"""
from pathlib import Path
import shutil
import time
from types import SimpleNamespace

import pytest

from datefixer.organize import organize_by_year


def _fake_stat_factory(ts: float):
    """Return a callable that can be used to monkeypatch Path.stat.

    The returned callable ignores `self` and returns an object with a
    ``st_birthtime`` attribute set to `ts`.
    """

    def _stat(_self):
        return SimpleNamespace(st_birthtime=ts)

    return _stat


def test_organize_dry_run_and_skip_non_files(tmp_path, monkeypatch):
    """Dry-run should return planned moves and should skip directories.

    Create one real file and one directory matching the glob. The
    directory must not be moved. Assert the returned moves contain only
    the real file and that no filesystem changes occurred.
    """
    # Setup: create a file and a directory matching the pattern
    monkeypatch.chdir(tmp_path)
    (tmp_path / "keep_dir").mkdir()
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"data")

    # provide a birthtime function rather than monkeypatching Path.stat
    ts = time.mktime((2020, 1, 2, 0, 0, 0, 0, 0, 0))
    def bt(p):
        return ts if p.name == "photo.jpg" else None

    dest = tmp_path / "out"
    moves = organize_by_year("*", dest, dry_run=True, birthtime_func=bt)

    # Only the file should be planned for moving (directory skipped)
    assert len(moves) == 1
    src, dst = moves[0]
    assert Path(src).name == "photo.jpg"
    assert dst.name == "photo.jpg"
    assert "2020" in str(dst)
    # original file still exists because dry_run
    assert f.exists()


def test_organize_actual_move_and_year_grouping(tmp_path, monkeypatch):
    """Actual run should move files into year folders based on birthtime.

    Create two files with different fake birth years and assert they are
    moved to separate year directories under the provided destination.
    """
    monkeypatch.chdir(tmp_path)
    f1 = tmp_path / "a.jpg"
    f2 = tmp_path / "b.jpg"
    f1.write_bytes(b"a")
    f2.write_bytes(b"b")

    # First file -> 2010, second file -> 2022
    ts1 = time.mktime((2010, 6, 1, 0, 0, 0, 0, 0, 0))
    ts2 = time.mktime((2022, 12, 31, 0, 0, 0, 0, 0, 0))

    mapping = {"a.jpg": ts1, "b.jpg": ts2}
    def bt_map(p):
        return mapping.get(p.name)

    dest = tmp_path / "grouped"
    moves = organize_by_year("*.jpg", dest, dry_run=False, birthtime_func=bt_map)

    # Expect two moves
    assert len(moves) == 2
    moved_names = {Path(dst).parent.name for (_src, dst) in moves}
    assert "2010" in moved_names
    assert "2022" in moved_names

    # Files should no longer exist in original location
    assert not (tmp_path / "a.jpg").exists()
    assert not (tmp_path / "b.jpg").exists()

    # And should be present under dest/year/
    assert (dest / "2010" / "a.jpg").exists()
    assert (dest / "2022" / "b.jpg").exists()


def test_non_matching_pattern_results_in_no_moves(tmp_path, monkeypatch):
    """When no files match the pattern, no moves should be returned."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "other.txt").write_text("x")
    dest = tmp_path / "out"
    moves = organize_by_year("*.jpg", dest, dry_run=True)
    assert moves == []
