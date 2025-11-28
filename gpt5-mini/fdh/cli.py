"""Command-line interface for fdh package."""
import argparse
from pathlib import Path
from . import exiftool, set_times, exif_setter, transcode, utils, date_mapper
from tqdm import tqdm


def cmd_set_system(args):
    # resolve simple glob patterns; Path.glob handles recursive /** patterns
    paths = list(Path().glob(args.pattern))
    files = [p for p in paths if p.is_file()]
    if args.dry_run:
        print("Dry run: would process", len(files), "files")
    for p in tqdm(files, disable=not args.progress):
        dt = None
        if args.use_exiftool:
            dt = exiftool.earliest_time_from_exiftool(p)
        if not dt:
            # fallback to filename inference
            dt = utils.infer_from_filename(p.name)
        if dt:
            set_times.apply_system_time(p, dt, dry_run=args.dry_run)
            print(f"SET: {p} -> {dt}")
        else:
            print(f"NO DATE: {p}")


def cmd_set_exif(args):
    files = list(Path().glob(args.pattern))
    filtered = [f for f in files if f.is_file()]
    for p in tqdm(filtered, disable=not args.progress):
        # support simple mapping like AllDates<-mtime
        tags = {}
        if args.tag and args.from_system:
            ts = p.stat().st_mtime
            tags[args.tag] = datetime_from_timestamp(ts).strftime(
                "%Y:%m:%d %H:%M:%S"
            )
        if tags:
            exif_setter.set_exif_tags(p, tags, dry_run=args.dry_run)


def datetime_from_timestamp(ts: float):
    from datetime import datetime
    return datetime.fromtimestamp(ts)


def cmd_transcode(args):
    files = list(Path().glob(args.pattern))
    files = [f for f in files if f.is_file()]
    out_suffix = args.suffix or ".mp4"
    for f in tqdm(files, disable=not args.progress):
        out = f.with_name(f.stem + ".reduced" + out_suffix)
        move_to = (
            Path(args.move_original_to) if args.move_original_to else None
        )
        transcode.transcode_video(
            f,
            out,
            crf=args.crf,
            max_width=args.max_width,
            dry_run=args.dry_run,
            move_original_to=move_to,
        )


def cmd_set_dates(args):
    # parse destinations list (comma separated)
    dests = [d.strip() for d in args.dest.split(",")] if args.dest else []
    src_tags = args.src or []
    src_backups = Path(args.src_backups) if args.src_backups else None

    files = list(Path().glob(args.pattern))
    files = [f for f in files if f.is_file()]

    for f in tqdm(files, disable=not args.progress):
        candidates = date_mapper.gather_candidates(
            f, src_tags=src_tags, src_backups=src_backups
        )

        chosen = None
        # if interactive requested, or multiple src tags/backups present,
        # or multiple candidates found -> prompt
        force_interactive = (
            args.interactive or len(src_tags) > 1 or bool(src_backups)
        )
        if force_interactive and len(candidates) > 1:
            print(f"\nFile: {f}")
            # show full exiftool output to help choice if requested
            if args.show_exiftool:
                print("EXIFTOOL DUMP:")
                import json
                print(json.dumps(exiftool.read_all_tags(f), indent=2))
            chosen = date_mapper.interactive_choose(candidates)
        else:
            # auto-select first candidate if present
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
        prog="fdh",
        description="File Date Helpers CLI",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_set = sub.add_parser(
        "set-system",
        help="Set filesystem times from EXIF or filename inference",
    )
    p_set.add_argument(
        "pattern",
        help="glob pattern to select files, e.g. './**/*.JPG'",
    )
    p_set.add_argument(
        "--no-exiftool",
        dest="use_exiftool",
        action="store_false",
        help="Don't use exiftool to read dates",
    )
    p_set.add_argument("--dry-run", action="store_true")
    p_set.add_argument("--progress", action="store_true", default=True)
    p_set.set_defaults(func=cmd_set_system)

    p_exif = sub.add_parser("set-exif", help="Set EXIF tags on files")
    p_exif.add_argument("pattern", help="glob pattern to select files")
    p_exif.add_argument("--tag", help="EXIF tag to set (e.g. AllDates)")
    p_exif.add_argument(
        "--from-system",
        action="store_true",
        help="Set tag value from system mtime",
    )
    p_exif.add_argument("--dry-run", action="store_true")
    p_exif.add_argument("--progress", action="store_true", default=True)
    p_exif.set_defaults(func=cmd_set_exif)

    p_tr = sub.add_parser(
        "transcode",
        help="Transcode videos with metadata preservation",
    )
    p_tr.add_argument("pattern", help="glob pattern for videos")
    p_tr.add_argument("--crf", type=int, default=23)
    p_tr.add_argument("--max-width", type=int)
    p_tr.add_argument("--suffix", help="output suffix (default .mp4)")
    p_tr.add_argument(
        "--move-original-to",
        help="directory to move originals into",
    )
    p_tr.add_argument("--dry-run", action="store_true")
    p_tr.add_argument("--progress", action="store_true", default=True)
    p_tr.set_defaults(func=cmd_transcode)

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
        action="append",
        help=(
            "Source tag(s) to read values from. Can be given multiple times, "
            "e.g. --src 'EXIF:Composite:SubSecDateTimeOriginal'"
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
