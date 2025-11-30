## datefixer

> A small, modular toolset to inspect and set filesystem timestamps and EXIF metadata, and to transcode videos while preserving metadata.

Usage (module):

- Run CLI via module: `python -m datefixer <command> [options]`

Or after `pip install .` you can use the console script `datefixer`.

Commands:
- `set-dates`   : Set filesystem or EXIF times from EXIF, reference files, or filename inference.
- `transcode` (# TODO): Transcode videos using sensible defaults (ffmpeg), copy metadata and set output timestamps.

---

### `set-dates`

> The `set-dates` subcommand is the primary tool to set dates on many files from EXIF, backups, or filename inference.

Usage example:

```zsh
datefixer set-dates "*.jpg" \
	--dest-tags "File:System:FileModifyDate,AllDates" \
	--src-tags "EXIF:Composite:SubSecDateTimeOriginal" \
	--backups_path="./backups" \
	--backups_tags="File:System:FileModifyDate,AllDates" \
	--update-systime
	--dry-run \
	--interactive \
	--progress
```

Key options and behavior:
- `pattern` (positional): glob pattern selecting files to operate on.
- `--src-tags`: Comma-separated source tags to read candidate datetimes from. Tags may be EXIF keys like `EXIF:ExifIFD:DateTimeOriginal` or filesystem selectors using the `File:System:` prefix (e.g. `File:System:FileModifyDate`).
- `--dest-tags`: Comma-separated list of destination tags to set. Destination tags may be EXIF keys (`AllDates` is supported) or filesystem selectors using `File:System:` (supported: `FileModifyDate`, `FileInodeChangeDate`, `CreatedDate`).
- `--backups-path`: Optional directory to search for files with the same name; matching files found here contribute candidate dates.
- `--backups-tags`: Comma-separated tags to read from backup files (same format as `--src-tags`). If omitted, all available tags are considered.
- `--interactive` / `-i`: Force interactive selection when multiple candidate dates are found for a file.
- `--show-exiftool`: When prompting interactively, print the raw `exiftool` JSON dump for the current file to aid inspection.
- `--dry-run`: Print commands and actions without modifying files. Highly recommended before running large batches.
- `--progress`: Show a progress bar (useful for large sets).

Notes on timestamps and EXIF
- Writing EXIF metadata with `exiftool` can also update filesystem timestamps (modification time, and on some platforms creation/birth time). The library's setter functions attempt to preserve system timestamps by default when possible; to intentionally update system timestamps you can call the programmatic API with `update_systime=True`. The CLI supports the `--update-systime` flag to allow updating system timestamps when writing EXIF.


Requirements:
- Python 3.8+
- `exiftool` (external binary) for robust EXIF reading/writing
- `ffmpeg` for `transcode` command
- Python packages: listed in `requirements.txt`

Installation (quick):

```bash
python -m pip install -r requirements.txt
# ensure exiftool and ffmpeg are available on PATH
```

Notes:
- This is a prototype intended to be readable and extensible. Commands use `exiftool` where possible for maximum compatibility, and fall back to python `exif`-based parsing when not available.
- Tests are simple and don't exercise external binaries.
- Tests are included; some are unit tests and some optionally exercise
	`exiftool` when available. To run the integration tests that need
	real images, put those test files under `tests/fixtures/` with the
	names described below.

Test fixtures and where to put your images
- Put any real images you want to use for integration under: `tests/fixtures/`
- The integration tests will run against files in `tests/fixtures/` and
	will skip exiftool-dependent checks if `exiftool` is not installed.

Note about filesystem (system) tags
- To read or write filesystem timestamps from the CLI use the
	``File:System:`` prefix. The supported system tags are:
	- ``File:System:FileModifyDate``  (modification time)
	- ``File:System:FileInodeChangeDate``  (inode/change time)
	- ``File:System:FileCreateDate``  (creation/birth time, platform dependent)

Note about EXIF tags:
- You can add `AllDates` as a dest tag.

When passing destination tags to the CLI or library functions, include one
of the above if you want to modify the corresponding system timestamp.
