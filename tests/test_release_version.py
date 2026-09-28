"""Current product version agrees across source, metadata and CLI."""

import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime/src"))
from origin_sciplot import __version__  # noqa: E402


def test_current_release_version_consistency():
    project = (ROOT / "runtime/pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version\s*=\s*"([^"]+)"', project, re.M).group(1)
    assert version == __version__ == "0.2.0"
    try:
        installed = metadata.version("editaplot-runtime")
    except metadata.PackageNotFoundError:
        installed = version  # Source checkout CLI uses the pyproject fallback.
    assert installed == version
    result = subprocess.run(
        [sys.executable, str(ROOT / "skill/editaplot/scripts/editaplot.py"), "--version"],
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "EditaPlot 0.2.0"
