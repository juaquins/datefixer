"""Command-line interface for fdh package."""
import argparse
from pathlib import Path
from . import exiftool, set_times, exif_setter, transcode, utils
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

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)
