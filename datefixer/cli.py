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
from importlib.metadata import version
from datetime import datetime
from . import set_dates as set_dates_mod
from . import transcode as transcode_mod
from . import organize as organize_mod
from . import search as search_mod
import glob

__version__ = version("datefixer")


def cmd_set_dates(args):
    """Wrapper that delegates to the `set_dates` module implementation.

    This wrapper extracts individual arguments from the argparse Namespace
    and passes them explicitly to the implementation.
    """
    _arg_dt = getattr(args, "dest_tags", None)
    dest_tags = [d.strip() for d in _arg_dt.split(",")] if _arg_dt else []

    _arg_st = getattr(args, "src_tags", None)
    src_tags = [s.strip() for s in _arg_st.split(",")] if _arg_st else []

    _arg_bt = getattr(args, "backups_tags", None)
    backups_tags = [b.strip() for b in _arg_bt.split(",")] if _arg_bt else []

    _arg_b = getattr(args, "backups_path", None)
    backups_path = Path(_arg_b) if _arg_b else None

    set_dates_mod.cmd_set_dates(
        pattern=args.pattern,
        dest_tags=dest_tags,
        src_tags=src_tags,
        backups_path=backups_path,
        backups_tags=backups_tags,
        interactive=bool(getattr(args, "interactive", False)),
        show_exiftool=bool(getattr(args, "show_exiftool", False)),
        dry_run=bool(getattr(args, "dry_run", False)),
        progress=bool(getattr(args, "progress", True)),
        update_systime=bool(getattr(args, "update_systime", False)),
    )


def cmd_transcode(args):
    """Handle the `transcode` subcommand."""
    src_pattern = args.src
    dst_arg = getattr(args, "dst", None)

    def _find_files(min_size_mb, regex=None):
        min_size_bytes = min_size_mb * 1024 * 1024
        matches = []
        if regex:
            for f in glob.glob(regex, recursive=True):
                f = Path(f)
                if (
                    f.is_file() and
                    f.stat().st_size >= min_size_bytes and
                    "originals" not in str(f) and
                    "reduced" not in str(f)
                ):
                    matches.append(f)
        else:
            all_exts = [".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv"]
            for ext in all_exts:
                for f in Path(".").rglob(f"*{ext}", case_sensitive=False):
                    if (
                        f.is_file() and
                        f.stat().st_size >= min_size_bytes and
                        "originals" not in str(f) and
                        "reduced" not in str(f)
                    ):
                        matches.append(f)
        return matches

    # If the user passed an explicit existing path, accept it regardless of min-size filtering
    sp = Path(src_pattern)
    if sp.exists() and sp.is_file():
        matches = [sp]
    else:
        matches = _find_files(args.min_size_mb, src_pattern)
    if not matches:
        print(f"No files match pattern: {src_pattern}")
        return

    # Helper to decide destination path for a given source
    def _dst_for(src_path: Path) -> Path:
        if dst_arg:
            dstp = Path(dst_arg)
            # If dst looks like a directory (exists as dir or has no suffix), use as directory
            if dstp.exists() and dstp.is_dir():
                return dstp / src_path.name
            if dstp.suffix == "":
                # treat as directory (create if needed)
                return dstp / src_path.name
            # otherwise treat as specific file path (only valid when single source)
            return dstp
        # default: place in same dir with '.reduced' inserted before suffix
        return src_path.with_name(f"{src_path.stem}.reduced{args.suffix or src_path.suffix}")

    # single source and dst may be a file path
    if len(matches) == 1:
        src_path = Path(matches[0])
        dst_path = _dst_for(src_path)
        move_to = Path(args.move_original_to) if args.move_original_to else None
        res = transcode_mod.transcode_video(
            src_path,
            dst_path,
            crf=args.crf,
            max_width=args.max_width,
            dry_run=args.dry_run,
            move_original_to=move_to,
        )
        if not res:
            raise SystemExit(1)
        return

    # multiple matches -> treat dst as directory (or default to each source dir)
    dest_dir = Path(dst_arg) if dst_arg else None
    if dest_dir and dest_dir.suffix != "":
        # if user passed a file-like dst for many sources, treat its parent as target dir
        dest_dir = dest_dir.parent
        print(f"Found {len(matches)} results, dest must be a directory. Using {dest_dir}")
    if dest_dir:
        dest_dir.mkdir(parents=True, exist_ok=True)

    for m in matches:
        src_path = Path(m)
        dst_path = _dst_for(src_path)
        move_to = Path(args.move_original_to) if args.move_original_to else None
        res = transcode_mod.transcode_video(
            src_path,
            dst_path,
            crf=args.crf,
            max_width=args.max_width,
            dry_run=args.dry_run,
            move_original_to=move_to,
        )
        if not res:
            print(f"transcode failed for {src_path}")


def cmd_organize(args):
    """Handle the `organize` subcommand."""
    dest = Path(args.dest_root)
    moves = organize_mod.organize_by_year(
        args.pattern,
        dest,
        dry_run=args.dry_run
    )
    print(f"Organized {len(moves)} files")


def cmd_search(args):
    """Handle the `search` subcommand (CLI wrapper).

    Delegates to `datefixer.search.search_files` and prints matches.
    """
    matches = search_mod.search_files(
        pattern=args.pattern,
        compare=getattr(args, "compare", None),
        move_to=getattr(args, "move_to", None),
        dry_run=bool(getattr(args, "dry_run", False)),
    )

    # If the user supplied a compare expression, extract tag names referenced
    tag_names = search_mod.parse_compare_tag_names(getattr(args, "compare", None))

    import json

    for m in matches:
        # For matched files, if tag names were provided, read EXIF tags and extract only date-like tags
        if tag_names:
            try:
                tags = search_mod.exiftool.read_all_tags(m)
            except Exception:
                tags = {}
            # If creation time was requested, attempt to inject it here as
            # well so CLI output matches the search behavior.
            wants_create = any(("file" in tn.lower() and "create" in tn.lower()) or tn.lower().replace(" ", "") == "file:system:filecreatedate" for tn in tag_names)
            if wants_create:
                try:
                    st = Path(m).stat()
                    birth_ts = getattr(st, "st_birthtime", None)
                    if birth_ts is not None:
                        from datetime import datetime as _dt

                        dt = _dt.fromtimestamp(birth_ts)
                        tags.setdefault("File:System:FileCreateDate", dt.strftime("%Y:%m:%d %H:%M:%S"))
                except Exception:
                    pass

            dates = {}
            for tn in tag_names:
                val = search_mod._find_tag_value(tags, tn)
                coerced = search_mod._coerce_value(val)
                if isinstance(coerced, datetime):
                    dates[tn] = coerced.isoformat()
            if dates:
                print(f"{m} {json.dumps(dates)}")
            else:
                print(m)
        else:
            print(m)
    print(f"Found {len(matches)} match(es).")


def main():
    parser = argparse.ArgumentParser(
        prog="datefixer",
        description="Datefixer CLI",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__
    )
    sub = parser.add_subparsers(dest="cmd")

    ###########################################
    # -------- subcommand: set-dates -------- #
    ###########################################
    p_sd = sub.add_parser("set-dates", help="Set destination tags from source tags / reference files / file name.")
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
            "the 'File:System:' prefix (supported: FileModifyDate, FileInodeChangeDate, FileCreateDate). "
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

    ###########################################
    # -------- subcommand: transcode -------- #
    ###########################################
    p_tc = sub.add_parser("transcode", help="Transcode files using ffmpeg.")
    p_tc.add_argument("src", help="Source video file")
    p_tc.add_argument("dst", help="Destination output file")
    p_tc.add_argument("--crf", type=int, default=23, help="CRF value for x265 encoding")
    p_tc.add_argument("--max-width", type=int, default=None, help="Max width to scale output to")
    p_tc.add_argument("--min-size-mb", type=int, default=100, help="Minimum size in MB (default: 100)")
    p_tc.add_argument("--dry-run", action="store_true", help="Print ffmpeg command instead of running it")
    p_tc.add_argument("--suffix", type=str, help="")
    p_tc.add_argument("--move-original-to", help="Optional folder to move original file into after transcode")
    p_tc.set_defaults(func=cmd_transcode)

    ###########################################
    # -------- subcommand: organize -------- #
    ###########################################
    p_org = sub.add_parser("organize", help="Organize files into YEAR folders based on inferred dates.")
    p_org.add_argument("pattern", help="Glob pattern to select files (e.g. '*.jpg')")
    p_org.add_argument("dest_root", help="Destination root folder to place organized files")
    p_org.add_argument("--dry-run", action="store_true", help="Do not move files; only print actions")
    p_org.set_defaults(func=cmd_organize)

    ###########################################
    # -------- subcommand: search -------- #
    ###########################################
    p_search = sub.add_parser("search", help="Search files using a glob pattern and optional EXIF tag comparison.")
    p_search.add_argument("pattern", help="Glob pattern to select files (e.g. '/path/**/*.jpg')")
    p_search.add_argument(
        "-c",
        "--compare",
        dest="compare",
        help=("Comparison expression between two EXIF tags, e.g. 'DateTimeOriginal > DateTimeDigitized'. "
              "Supported operators: > >= < <= == != <>")
    )
    p_search.add_argument(
        "-m",
        "--move-to",
        dest="move_to",
        help="Optional directory to move matched files into",
    )
    p_search.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not move files; only print matches",
    )
    p_search.set_defaults(func=cmd_search)

    ###########################################

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)
