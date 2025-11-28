"""Command-line interface for datefixer package."""
import argparse
from pathlib import Path
from . import exiftool, date_mapper
from tqdm import tqdm
import json


def cmd_set_dates(args):
    # parse destinations list (comma separated)
    dests = [d.strip() for d in args.dest.split(",")] if args.dest else []
    # --src is now comma-separated list
    src_tags = [s.strip() for s in args.src.split(",")] if args.src else []
    src_backups = Path(args.src_backups) if args.src_backups else None

    files = list(Path().glob(args.pattern))
    files = [f for f in files if f.is_file()]

    for f in tqdm(files, disable=not args.progress):
        candidates = date_mapper.gather_candidates(
            f, src_tags=src_tags, src_backups=src_backups
        )

        chosen = None
        force_interactive = (
            args.interactive or len(src_tags) > 1 or bool(src_backups)
        )
        if force_interactive and len(candidates) > 1:
            print(f"\nFile: {f}")
            if args.show_exiftool:
                print("EXIFTOOL DUMP:")
                print(json.dumps(exiftool.read_all_tags(f), indent=2))
            chosen = date_mapper.interactive_choose(candidates)
        else:
            if candidates:
                chosen = candidates[0][1]

        if chosen:
            date_mapper.apply_destinations(
                f, dests, chosen, dry_run=args.dry_run
            )
            print(f"APPLIED {f} -> {chosen}")
        else:
            print(f"SKIPPED {f} (no choice)")


def main():
    parser = argparse.ArgumentParser(
        prog="datefixer",
        description="Datefixer CLI",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_sd = sub.add_parser(
        "set-dates",
        help=(
            "Set one or more destination tags from one or more source tags or "
            "reference backups"
        ),
    )
    p_sd.add_argument("pattern", help="glob pattern to select files")
    p_sd.add_argument(
        "--dest",
        required=True,
        help=(
            "Comma-separated list of destination tags, e.g. "
            "'File:System:FileModifyDate,EXIF:AllDates'"
        ),
    )
    p_sd.add_argument(
        "--src",
        help=(
            "Comma-separated source tag(s) to read values from. "
            "e.g. --src 'EXIF:Composite:SubSecDateTimeOriginal,"
            "EXIF:GPS:GPSDateTime'"
        ),
    )
    p_sd.add_argument(
        "--src-backups",
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
    p_sd.add_argument("--progress", action="store_true", default=True)
    p_sd.set_defaults(func=cmd_set_dates)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)
