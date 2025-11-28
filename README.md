datefixer — File Date Helpers (prototype)

A small, modular toolset to inspect and set filesystem timestamps and EXIF metadata, and to transcode videos while preserving metadata.

Usage (module):

- Run CLI via module: `python -m datefixer <command> [options]`

Or after `pip install .` you can use the console script `datefixer`.

Commands:
- `set-system`  : Set system (filesystem) times from EXIF, reference files, or filename inference.
- `set-exif`    : Set EXIF tags on files from system times or other EXIF tags.
- `transcode`   : Transcode videos using sensible defaults (ffmpeg), copy metadata and set output timestamps.

Common options:
- `--glob` / `--pattern` : glob to select files (supports recursive globs)
- `--dry-run` : show what would be done, don't change files
- `--progress` : enable tqdm progress bars (default on)

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
- Put any real images you want to use for integration under:
	`file-date-helpers/gpt5-mini/tests/fixtures/`
- The integration test expects one sample named `sample1.jpg`.
- You can add additional files; tests will skip integration checks if
	`exiftool` is not installed.
