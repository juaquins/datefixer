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
        if force_interactive or len(candidates) > 1:
            print(f"\nFile: {file_to_fix}")
            if args.show_exiftool:
                print("EXIFTOOL DUMP:")
                print(json.dumps(exiftool.read_all_tags(file_to_fix), indent=2))
            chosen_dt = date_mapper.interactive_choose(candidates)
        else:
            chosen_dt = candidates[0][1] if candidates else None

        if chosen_dt:
            # update_systime is True when the user asked to allow updating system timestamps
            update_systime = bool(getattr(args, "update_systime", False))
            # Pass the update_systime kwarg when supported; for
            # backwards compatibility detect older parameter names.
            try:
                from inspect import signature

                sig = signature(date_mapper.apply_destinations)
                if "update_systime" in sig.parameters:
                    date_mapper.apply_destinations(
                        file_to_fix,
                        dest_tags,
                        chosen_dt,
                        dry_run=args.dry_run,
                        update_systime=update_systime,
                    )
                else:
                    # Call the modern API passing `update_systime`.
                    date_mapper.apply_destinations(
                        file_to_fix,
                        dest_tags,
                        chosen_dt,
                        dry_run=args.dry_run,
                        update_systime=update_systime,
                    )
            except Exception:
                # Fallback to calling without the extra kwarg.
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
            "Comma-separated source tag(s) to read values from. Each tag may be an EXIF key "
            "(e.g. 'EXIF:ExifIFD:DateTimeOriginal') or a filesystem selector using the 'File:System:' prefix "
            "(e.g. 'File:System:FileModifyDate'). Example: --src-tags 'EXIF:Composite:SubSecDateTimeOriginal,EXIF:GPS:GPSDateTime'"
        ),
    )
    p_sd.add_argument(
        "--dest-tags",
        required=True,
        help=(
            "Comma-separated list of destination tags to set, e.g. 'File:System:FileModifyDate,EXIF:AllDates'. "
            "Destination tags may be EXIF keys (like 'EXIF:AllDates' or 'EXIF:ExifIFD:DateTimeOriginal') or filesystem selectors using "
            "the 'File:System:' prefix (supported: FileModifyDate, FileInodeChangeDate, CreatedDate). "
            "Note: writing EXIF tags may update filesystem modification time; the library preserves mtime by default when possible."
        ),
    )
    p_sd.add_argument(
        "--backups-path",
        help=(
            "Optional reference folder to search for files with the same name. "
            "If a matching filename is found under this folder, EXIF or filesystem timestamps from the backup file will be used as additional candidates. "
            "Example: --backups-path /mnt/backups"
        ),
    )
    p_sd.add_argument(
        "--backups-tags",
        help=(
            "Comma-separated list of tags to read from backup files (same format as --src-tags). "
            "Defaults to all available tags when omitted. Example: --backups-tags 'EXIF:IFD0:ModifyDate'"
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
    p_sd.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Do not modify files. Print the actions/commands that would be run instead. "
            "Useful for verification before performing large batch operations."
        ),
    )
    p_sd.add_argument(
        "--progress",
        action="store_true",
        help=(
            "Show a progress bar for long-running operations. Disable for quiet/batched runs."
        ),
    )
    p_sd.add_argument(
        "--update-systime",
        action="store_true",
        help=(
            "Allow updating system timestamps (mtime/creation) when writing EXIF. "
            "By default the tool will attempt to preserve system timestamps when possible; use this flag to permit updates."
        ),
    )
    p_sd.set_defaults(func=cmd_set_dates)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)
