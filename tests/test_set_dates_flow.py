from datefixer import cli, date_mapper
from datetime import datetime


def test_set_dates_flow_monkeypatched(monkeypatch, tmp_path):
    """Exercise the CLI handler with monkeypatched internals.

    This test avoids invoking the actual CLI process by calling the
    subcommand handler directly. It monkeypatches :func:`gather_candidates`
    and :func:`apply_destinations` so the flow is deterministic and side
    effects are avoided.
    """
    # create a fake file
    f = tmp_path / "photo.jpg"
    f.write_text("x")

    # mock gather_candidates to return two candidates
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

    # build args namespace similar to argparse
    # run CLI from the tmp_path so a relative glob works
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
    # run the cli handler directly
    cli.cmd_set_dates(args)

    assert calls['path'].endswith('photo.jpg')
    assert 'File:System:FileModifyDate' in calls['dests'][0]
    assert calls['dry'] is True
