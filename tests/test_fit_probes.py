"""Real desktop checks are opt-in and use separate, disposable projects."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "runtime" / "src", ROOT / "tools" / "probes"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def test_grapher_native_statistics_parser() -> None:
    from fit_grapher import parse_statistics

    text = "Equation Y = 1.97 * X - 0.15\nCoefficient of determination, R-sq'd = 0.99889324"
    assert parse_statistics(text) == {"slope": 1.97, "intercept": -0.15, "r_squared": 0.99889324}
    with pytest.raises(ValueError):
        parse_statistics("No native statistics")


def _run_probe(name: str, directory: Path) -> dict:
    process = subprocess.run(  # noqa: S603 - repository-owned probe script
        [sys.executable, str(ROOT / "tools" / "probes" / f"fit_{name}.py"), str(directory)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONPATH": str(ROOT / "runtime" / "src")},
        check=False,
    )
    report = json.loads((directory / f"fit_{name}.json").read_text(encoding="utf-8"))
    assert process.returncode == 0, (report.get("error"), process.stderr[-500:])
    return report


@pytest.mark.grapher
@pytest.mark.skipif(os.name != "nt", reason="Grapher COM requires Windows")
def test_grapher_native_linear_fit_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("pythoncom")
    from grapher_sciplot.smoke import SmokeFailure, discover

    try:
        discover()
    except SmokeFailure as exc:
        pytest.skip(str(exc))
    report = _run_probe("grapher", tmp_path / "grapher")
    assert report["status"] == "ok", report.get("error")
    assert Path(report["artifacts"]["grf"]).read_bytes().startswith(b"Grapher")
    assert report["readback"]["fit_count"] == 1
    assert report["readback"]["fit_type"] == 0
    assert (report["readback"]["x_column"], report["readback"]["y_column"]) == (1, 2)
    assert report["result"]["slope"] == pytest.approx(1.97, abs=1e-6)
    assert report["result"]["intercept"] == pytest.approx(0.15, abs=1e-6)
    assert report["result"]["r_squared"] == pytest.approx(0.998893235869, abs=1e-7)
    assert report["teardown_error"] is None


@pytest.mark.origin
@pytest.mark.skipif(os.name != "nt", reason="Origin automation requires Windows")
def test_origin_native_linear_fit_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("originpro")
    report = _run_probe("origin", tmp_path / "origin")
    assert report["status"] == "ok", report.get("error")
    assert Path(report["artifacts"]["opju"]).is_file()
    assert report["readback"]["report_sheet_exists"]
    assert report["readback"]["curve_sheet_exists"]
    assert report["readback"]["model"] == "y = a + b*x"
    assert report["readback"]["source_x"] == [1, 2, 3, 4, 5]
    assert report["result"]["slope"] == pytest.approx(1.97, abs=1e-8)
    assert report["result"]["intercept"] == pytest.approx(0.15, abs=1e-8)
    assert report["result"]["r_squared"] == pytest.approx(0.998893235869, abs=1e-8)
