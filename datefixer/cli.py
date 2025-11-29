"""Command-line interface for the ``datefixer`` package.

This module exposes the CLI entrypoint used by the console script
``datefixer``. It contains a thin adapter from parsed arguments to the
library functions in :mod:`datefixer.date_mapper` and
:mod:`datefixer.exiftool`.

The CLI functions are small and intentionally call into the package
API so tests can exercise logic without spawning subprocesses.
"""
import argparse
from pathlib import Path
from . import exiftool, date_mapper
from tqdm import tqdm
import json


def cmd_set_dates(args):
    """Handle the ``set-dates`` subcommand.

    Args:
        args: argparse.Namespace produced by the argument parser.
            Expected attributes include: ``pattern``, ``dest``, ``src``,
            ``backups_path``, ``interactive``, ``show_exiftool``,
            ``backups_tags``, ``dry_run``, and ``progress``.
    """
    dest_tags = [d.strip() for d in args.dest_tags.split(",")] if args.dest_tags else []
    src_tags = [s.strip() for s in args.src_tags.split(",")] if args.src_tags else []
    backups_path = Path(args.backups_path) if args.backups_path else None
    backups_tags = [
        s.strip() for s in args.backups_tags.split(",")
    ] if args.backups_tags else []

    # TODO: simplify
    # this seems more complicated than it needs to be if we were using glob.glob
    # ---
    # Support absolute and relative glob patterns. If an absolute pattern is
    # provided (e.g. /tmp/*.jpg), Path.glob on the current working directory
    # will raise. Detect that case and run the glob on the pattern's parent
    # directory instead.
    pattern_path = Path(args.pattern)
    if pattern_path.is_absolute():
        parent = pattern_path.parent
        name = pattern_path.name
        files = list(parent.glob(name))
    else:
        files = list(Path().glob(args.pattern))
    files = [f for f in files if f.is_file()]

    for file_to_fix in tqdm(files, disable=not args.progress):
        candidates = date_mapper.gather_candidates(
            file_to_fix,
            src_tags=src_tags,
            backups_path=backups_path,
            backups_tags=backups_tags,
        )

        force_interactive = (
            args.interactive  # or len(src_tags) > 1 or bool(backups_path)
        )
        if force_interactive and len(candidates) > 1:
            print(f"\nFile: {file_to_fix}")
            if args.show_exiftool:
                print("EXIFTOOL DUMP:")
                print(json.dumps(exiftool.read_all_tags(file_to_fix), indent=2))
            chosen_dt = date_mapper.interactive_choose(candidates)
        else:
            chosen_dt = candidates[0][1] if candidates else None

        if chosen_dt:
            date_mapper.apply_destinations(
                file_to_fix, dest_tags, chosen_dt, dry_run=args.dry_run
            )
            print(f"APPLIED {file_to_fix} -> {chosen_dt}")
        else:
            print(f"SKIPPED {file_to_fix} (no choice)")


def main():
    parser = argparse.ArgumentParser(
        prog="datefixer",
        description="Datefixer CLI",
    )
    sub = parser.add_subparsers(dest="cmd")

    # -------- subcommand: set-dates -------- #
    p_sd = sub.add_parser(
        "set-dates",
        help=(
            "Set one or more destination tags from one or more source tags or "
            "reference backups"
        ),
    )
    p_sd.add_argument("pattern", help="glob pattern to select files")
    p_sd.add_argument(
        "--src-tags",
        help=(
            "Comma-separated source tag(s) to read values from. "
            "e.g. --src-tags 'EXIF:Composite:SubSecDateTimeOriginal,"
            "EXIF:GPS:GPSDateTime'"
        ),
    )
    p_sd.add_argument(
        "--dest-tags",
        required=True,
        help=(
            "Comma-separated list of destination tags, e.g. "
            "'File:System:FileModifyDate,EXIF:AllDates'. "
            "To modify filesystem timestamps include one of: "
            "File:System:FileModifyDate, File:System:FileInodeChangeDate, "
            "File:System:FileCreateDate"
        ),
    )
    p_sd.add_argument(
        "--backups-path",
        help=(
            "Reference folder to search for matching filenames to obtain "
            "dates"
        ),
    )
    p_sd.add_argument(
        "--backups-tags",
        help=(
            "Reference folder to search for matching filenames to obtain "
            "dates"
        ),
    )
    p_sd.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Force interactive selection for each file",
    )
    p_sd.add_argument(
        "--show-exiftool",
        action="store_true",
        help="Print full exiftool JSON dump when prompting",
    )
    p_sd.add_argument("--dry-run", action="store_true")
    p_sd.add_argument("--progress", action="store_true")
    p_sd.set_defaults(func=cmd_set_dates)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)
