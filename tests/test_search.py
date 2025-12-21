"""Integration tests for `datefixer.search` based on real fixture metadata.

These tests exercise the `search.search_files` function against the
repository's sample media files found under `tests/fixtures/`. They rely
on the external `exiftool` binary via the project's `datefixer.exiftool`
helper. If `exiftool` is not available on PATH the tests are skipped.

Test goals and coverage:
- Verify `exiftool.read_all_tags` returns data for fixture images.
- For each fixture image, pick a representative tag (prefer date/time
  related tags) and assert that `search.search_files` with a compare
  expression matching that tag=value returns the file.
- Verify `search.search_files` move behavior using a copied fixture
  (dry-run and actual move) and collision-avoidance.

These tests intentionally discover tag keys/values at runtime so they
remain robust to minor metadata variations while still validating the
end-to-end behavior of the search DSL.
"""
import shutil
import pytest
from pathlib import Path
from datefixer import exiftool, search
from datefixer import utils


# Skip the whole module when exiftool is not available
pytestmark = pytest.mark.skipif(not exiftool.has_exiftool(), reason="exiftool not available")


FIXTURES_DIR = Path("tests/fixtures")


def test_fixtures_provide_tags():
    """Ensure fixture files return a non-empty mapping of EXIF tags.

    This catches cases where exiftool is missing or the fixture files are
    unreadable.
    """
    allowed = {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".raw", ".arw", ".cr2", ".nef"}
    files = [f for f in FIXTURES_DIR.iterdir() if f.is_file() and f.suffix.lower() in allowed]
    assert files, "no fixture files found"
    for f in files:
        tags = exiftool.read_all_tags(f)
        assert isinstance(tags, dict)
        assert tags, f"expected tags for fixture {f}"


def test_search_matches_fixture_by_tag():
    """For each fixture, pick a tag and ensure the search DSL finds it.

    The test prefers tags that contain 'Date' or 'Time' (common and
    stable across images). If none are found, the first available tag
    is used. The test builds an expression of the form ``Tag == Value``
    and asserts that `search.search_files` returns the fixture filename.
    """
    allowed = {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".raw", ".arw", ".cr2", ".nef"}
    for f in [f for f in FIXTURES_DIR.iterdir() if f.is_file() and f.suffix.lower() in allowed]:
        tags = exiftool.read_all_tags(f)
        assert tags, f"no tags for {f}"
        # Prefer date/time-like tags
        chosen = None
        for k in tags:
            if any(tok in k for tok in ("Date", "Time", "Create", "Modify")):
                chosen = (k, tags[k])
                break
        if not chosen:
            chosen = next(iter(tags.items()))

        key, val = chosen
        expr = f"{key} == {val}"
        # use the fixture's extension so the glob matches the file type
        pattern = str(FIXTURES_DIR / f"*{f.suffix}")
        res = search.search_files(pattern, compare=expr, dry_run=True)
        # May be returned as Path or str — normalize names
        names = {Path(p).name for p in res}
        assert f.name in names, f"expected {f.name} to be found by expr {expr}"


def test_search_move_and_dry_run(tmp_path):
    """Verify move-to behavior: dry-run does not move; actual move does.

    Use a copy of one fixture so tests do not modify repository files.
    """
    src = FIXTURES_DIR / "IMG_20240331_212928.jpg"
    assert src.exists()
    copy = tmp_path / src.name
    shutil.copy2(src, copy)

    # Choose a tag from the copied file
    tags = exiftool.read_all_tags(copy)
    key, val = next(iter(tags.items()))

    dest = tmp_path / "dest"
    dest.mkdir()

    # dry-run -> file should remain
    res = search.search_files(str(copy.parent / "*.jpg"), compare=f"{key} == {val}", move_to=str(dest), dry_run=True)
    assert any(Path(p).name == copy.name for p in res)
    assert copy.exists()

    # actual move -> file should be moved
    res2 = search.search_files(str(copy.parent / "*.jpg"), compare=f"{key} == {val}", move_to=str(dest), dry_run=False)
    assert any(Path(p).name != copy.name or not copy.exists() for p in res2)


def test_and_or_chaining_on_fixture():
    """Verify that `&` (AND) and `|` (OR) chaining work for a fixture.

    This test picks two tags from the sample JPEG and builds expressions
    that should and should not match to assert correct logical grouping.
    """
    f = FIXTURES_DIR / "IMG_20240331_212928.jpg"
    tags = exiftool.read_all_tags(f)
    assert tags, "expected tags for fixture"
    # pick two distinct tag keys
    keys = list(tags.keys())[:2]
    if len(keys) < 2:
        pytest.skip("not enough tags in fixture to test chaining")
    k1, k2 = keys[0], keys[1]
    v1, v2 = tags[k1], tags[k2]

    # AND should match when both equal
    expr_and = f"{k1} == {v1} & {k2} == {v2}"
    res_and = search.search_files(str(FIXTURES_DIR / "*.jpg"), compare=expr_and, dry_run=True)
    names_and = {Path(p).name for p in res_and}
    assert f.name in names_and

    # AND should not match when second term false
    expr_and_false = f"{k1} == {v1} & {k2} == SOME_IMPOSSIBLE_VALUE"
    res_and_false = search.search_files(str(FIXTURES_DIR / "*.jpg"), compare=expr_and_false, dry_run=True)
    assert all(Path(p).name != f.name for p in res_and_false)

    # OR should match when first term true even if second false
    expr_or = f"{k1} == {v1} | {k2} == SOME_IMPOSSIBLE_VALUE"
    res_or = search.search_files(str(FIXTURES_DIR / "*.jpg"), compare=expr_or, dry_run=True)
    names_or = {Path(p).name for p in res_or}
    assert f.name in names_or


def test_literal_date_comparison_gt_and_lt():
    """Test comparing a date tag against a literal date with > and <.

    The test finds a date-like tag on the fixture, parses it, then compares
    against a literal older and newer date to exercise both '>' and '<'.
    """
    f = FIXTURES_DIR / "IMG_20240331_212928.jpg"
    tags = exiftool.read_all_tags(f)
    # find a date-like tag
    date_tag = None
    for k, v in tags.items():
        if "Date" in k or "Time" in k:
            date_tag = (k, v)
            break
    if not date_tag:
        pytest.skip("no date-like tag found in fixture")
    k, v = date_tag
    parsed = utils.parse_date(v)
    assert parsed is not None, "could not parse fixture date tag"

    # older literal (one year earlier)
    older = parsed.replace(year=parsed.year - 1)
    older_literal = older.strftime("%Y:%m:%d %H:%M:%S")
    res_gt = search.search_files(str(FIXTURES_DIR / "*.jpg"), compare=f"{k} > {older_literal}", dry_run=True)
    assert any(Path(p).name == f.name for p in res_gt)

    # newer literal (one year later) should not match as '>'
    newer = parsed.replace(year=parsed.year + 1)
    newer_literal = newer.strftime("%Y:%m:%d %H:%M:%S")
    res_lt = search.search_files(str(FIXTURES_DIR / "*.jpg"), compare=f"{k} < {newer_literal}", dry_run=True)
    assert any(Path(p).name == f.name for p in res_lt)


def test_search_create_time(tmp_path):
    '''Checks that filesystem create time tag is working,
     which calls the MacOS SetDates command (vs exiftool)

    `datefixer search --compare "File:System:FileCreateDate >
    File:System:FileModifiedDate | File:System:FileCreateDate <>
    EXIF:ExifIFD:DateTimeOriginal "./*"`
    '''
    # Create a sample file and provide fake tags via exiftool.read_all_tags.
    f = tmp_path / "ct.jpg"
    f.write_text("x")

    def fake_read(path):
        # create time is newer than modified time, and different from EXIF original
        return {
            "File:System:FileCreateDate": "2021:01:02 00:00:00",
            "File:System:FileModifiedDate": "2021:01:01 00:00:00",
            "EXIF:ExifIFD:DateTimeOriginal": "2020:01:01 00:00:00",
        }

    # Monkeypatch exiftool.read_all_tags at runtime
    from datefixer import exiftool as _et
    orig = _et.read_all_tags
    _et.read_all_tags = fake_read
    try:
        expr = (
            "File:System:FileCreateDate > File:System:FileModifiedDate | "
            "File:System:FileCreateDate <> EXIF:ExifIFD:DateTimeOriginal"
        )
        res = search.search_files(str(tmp_path / "*.jpg"), compare=expr, dry_run=True)
        names = {Path(p).name for p in res}
        assert f.name in names
    finally:
        _et.read_all_tags = orig


def test_search_exiftool_special(tmp_path):
    '''Checks exiftool special tag syntax AllDates'''
    f = tmp_path / "all.jpg"
    f.write_text("x")

    def fake_read(path):
        return {"AllDates": "2020:01:01 00:00:00"}

    from datefixer import exiftool as _et
    orig = _et.read_all_tags
    _et.read_all_tags = fake_read
    try:
        res = search.search_files(str(tmp_path / "*.jpg"), compare="AllDates == 2020:01:01 00:00:00", dry_run=True)
        names = {Path(p).name for p in res}
        assert f.name in names
    finally:
        _et.read_all_tags = orig


def test_parse_compare_tag_names():
    """Unit tests for `parse_compare_tag_names` parsing simple and chained expressions."""
    from datefixer import search as _s

    assert _s.parse_compare_tag_names(None) == []
    assert _s.parse_compare_tag_names("") == []
    expr = "DateTimeOriginal > DateTimeDigitized"
    assert _s.parse_compare_tag_names(expr) == ["DateTimeOriginal", "DateTimeDigitized"]

    expr2 = "A == B & C == D | E == F"
    # order should be first-seen
    assert _s.parse_compare_tag_names(expr2) == ["A", "B", "C", "D", "E", "F"]


def test_search_injects_file_create_date(tmp_path, monkeypatch):
    """Ensure `search_files` injects `File:System:FileCreateDate` from st_birthtime when requested.

    This test monkeypatches `exiftool.read_all_tags` to return an empty mapping
    (so injection is necessary). It uses the real filesystem birthtime
    returned by `Path.stat().st_birthtime` and skips the test if the
    platform does not expose it.
    """
    from datefixer import search as _s

    p = tmp_path / "c.jpg"
    p.write_text("x")

    # stub exiftool to return no tags so injection is necessary
    monkeypatch.setattr(_s.exiftool, "read_all_tags", lambda path: {})

    st = p.stat()
    birth_ts = getattr(st, "st_birthtime", None)
    if birth_ts is None:
        pytest.skip("filesystem does not expose st_birthtime on this platform")

    from datetime import datetime, timedelta

    birth_dt = datetime.fromtimestamp(birth_ts)
    # pick an older literal (one day earlier) so the compare should be True
    older = birth_dt - timedelta(days=1)
    older_literal = older.strftime("%Y:%m:%d %H:%M:%S")

    comp = f"File:System:FileCreateDate > {older_literal}"
    res = _s.search_files(str(tmp_path / "*.jpg"), compare=comp, dry_run=True)
    names = {Path(x).name for x in res}
    assert p.name in names
