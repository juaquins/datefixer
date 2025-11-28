import subprocess
import sys


def test_cli_help_runs():
    # Run the console script help (works when installed as package). Fallback
    # to invoking module - this will run in local env where package may not
    # be installed; so run 'python -m datefixer --help'
    cmd = [sys.executable, "-m", "datefixer", "--help"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "set-dates" in res.stdout
