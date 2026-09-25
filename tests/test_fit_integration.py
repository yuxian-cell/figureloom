"""Production RenderPlan -> native Scatter + Linear Fit -> reopen -> verify."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "runtime" / "src", ROOT / "skill" / "editaplot" / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import editaplot_core as core  # noqa: E402
from editaplot_engine.fit_contract import FitSpec  # noqa: E402
from grapher_sciplot.smoke import SmokeFailure, discover  # noqa: E402


def _plan(tmp_path: Path, *, with_error: bool = False) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "fit.csv"
    source.write_text(
        "X,Y,Y_SD\n1,2.1,0.20\n2,4.0,0.25\n3,6.2,0.30\n4,8.1,0.22\n5,9.9,0.28\n"
        if with_error else "X,Y\n1,2.1\n2,4.0\n3,6.2\n4,8.1\n5,9.9\n",
        encoding="ascii",
    )
    mapping = {"assignments": {"X": "x", "Y": "series"}}
    if with_error:
        mapping["assignments"]["Y_SD"] = "error"
    understanding = core.understand_data(
        source, template_id="scatter", mapping=mapping, engine_home=ROOT / "runtime"
    )
    plan = core.build_plan(
        source,
        template_id="scatter",
        claim="Y increases linearly with X.",
        evidence_role="relationship",
        mapping=mapping,
        semantic_confirmation=understanding["confirmation_gate"]["confirmation_payload_template"],
        fit_spec=FitSpec(model="linear", x_column="X", y_column="Y").to_dict(),
        engine_home=ROOT / "runtime",
    )
    plan_file = tmp_path / "render-plan.json"
    plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan_file


def _run_cli(*arguments: str) -> dict:
    process = subprocess.run(  # noqa: S603 - local project CLI and test-created paths
        [sys.executable, str(ROOT / "skill" / "editaplot" / "scripts" / "editaplot.py"), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    assert process.returncode == 0, process.stderr[-1000:] or process.stdout[-1000:]
    start = process.stdout.rfind("\n{") + 1
    return json.loads(process.stdout[start:])


@pytest.mark.grapher
@pytest.mark.skipif(os.name != "nt", reason="Grapher COM requires Windows")
def test_production_grapher_scatter_linear_fit(tmp_path: Path) -> None:
    pytest.importorskip("pythoncom")
    try:
        discover()
    except SmokeFailure as exc:
        pytest.skip(str(exc))
    plan_file = _plan(tmp_path)
    output = tmp_path / "grapher"
    rendered = _run_cli("render", str(plan_file), "--engine", "grapher", "--output-dir", str(output))
    verified = _run_cli("verify", str(output), "--engine", "grapher")
    assert rendered["status"] == verified["status"] == "ok"
    assert Path(rendered["editable"]).read_bytes().startswith(b"Grapher")
    assert Path(rendered["exports"]["png"]).read_bytes().startswith(b"\x89PNG")
    assert Path(rendered["exports"]["pdf"]).read_bytes().startswith(b"%PDF")
    assert verified["checks"]["native_fit"]
    assert verified["checks"]["line_symbol_mode"]
    assert verified["readback"]["plots"][0]["line_enabled"] is False
    assert verified["readback"]["legends"][0]["entries"] == ["Y", "Linear Fit - Y"]
    assert verified["readback"]["fit"]["result"]["parameters"]["slope"] == pytest.approx(1.97, abs=1e-6)
    assert verified["readback"]["fit"]["result"]["statistics"]["r_squared"] == pytest.approx(
        0.998893235869, abs=1e-7
    )


@pytest.mark.origin
@pytest.mark.skipif(os.name != "nt", reason="Origin automation requires Windows")
def test_production_origin_scatter_linear_fit(tmp_path: Path) -> None:
    pytest.importorskip("originpro")
    if not core.discover_origin_application()["launch_registration_detected"]:
        pytest.skip("Origin isolated COM registration is unavailable")
    plan_file = _plan(tmp_path)
    output = tmp_path / "origin"
    rendered = _run_cli(
        "render", str(plan_file), "--engine", "origin", "--engine-home", str(ROOT / "runtime"),
        "--python", sys.executable, "--output-dir", str(output),
    )
    verified = _run_cli("verify", str(output), "--engine", "origin")
    assert rendered["status"] == verified["status"] == "ok"
    for suffix in ("opju", "png", "pdf", "tif"):
        assert (output / f"result.{suffix}").stat().st_size > 0
    assert verified["checks"]["native_fit"]
    assert verified["readback"]["fit"]["scatter_plot_count"] == 2
    assert verified["readback"]["fit"]["result"]["parameters"]["intercept"] == pytest.approx(
        0.15, abs=1e-8
    )
    assert verified["readback"]["fit"]["result"]["statistics"]["r_squared"] == pytest.approx(
        0.998893235869, abs=1e-8
    )


def _assert_fit_unchanged(fit_only: dict, with_error: dict) -> None:
    for parameter in ("slope", "intercept"):
        assert with_error["parameters"][parameter] == pytest.approx(
            fit_only["parameters"][parameter], abs=1e-6
        )
    assert with_error["statistics"]["r_squared"] == pytest.approx(
        fit_only["statistics"]["r_squared"], abs=1e-7
    )
    assert fit_only["weight_mode"] == with_error["weight_mode"] == "none"
    assert fit_only["result_source"] == with_error["result_source"] == "backend_native"


@pytest.mark.grapher
@pytest.mark.skipif(os.name != "nt", reason="Grapher COM requires Windows")
def test_production_grapher_scatter_error_linear_fit(tmp_path: Path) -> None:
    pytest.importorskip("pythoncom")
    try:
        discover()
    except SmokeFailure as exc:
        pytest.skip(str(exc))
    baseline_plan = _plan(tmp_path / "baseline")
    combo_plan = _plan(tmp_path / "combo", with_error=True)
    baseline = tmp_path / "grapher-fit-only"
    combo = tmp_path / "grapher-error-fit"
    _run_cli("render", str(baseline_plan), "--engine", "grapher", "--output-dir", str(baseline))
    _run_cli("render", str(combo_plan), "--engine", "grapher", "--output-dir", str(combo))
    fit_only = _run_cli("verify", str(baseline), "--engine", "grapher")
    verified = _run_cli("verify", str(combo), "--engine", "grapher")
    assert fit_only["status"] == verified["status"] == "ok"
    assert all(verified["checks"][key] for key in (
        "document_reopened", "plot_binding", "error_bindings", "native_fit", "line_symbol_mode"
    ))
    assert verified["readback"]["plots"][0]["line_enabled"] is False
    assert verified["readback"]["plots"][0]["error"]["column"] == "Y_SD"
    assert verified["readback"]["legends"][0]["entries"] == ["Y", "Linear Fit - Y"]
    _assert_fit_unchanged(fit_only["readback"]["fit"]["result"], verified["readback"]["fit"]["result"])
    for suffix in ("grf", "png", "pdf"):
        assert (combo / f"result.{suffix}").stat().st_size > 0


@pytest.mark.origin
@pytest.mark.skipif(os.name != "nt", reason="Origin automation requires Windows")
def test_production_origin_scatter_error_linear_fit(tmp_path: Path) -> None:
    pytest.importorskip("originpro")
    if not core.discover_origin_application()["launch_registration_detected"]:
        pytest.skip("Origin isolated COM registration is unavailable")
    baseline_plan = _plan(tmp_path / "baseline")
    combo_plan = _plan(tmp_path / "combo", with_error=True)
    baseline = tmp_path / "origin-fit-only"
    combo = tmp_path / "origin-error-fit"
    render_args = ("--engine", "origin", "--engine-home", str(ROOT / "runtime"), "--python", sys.executable)
    _run_cli("render", str(baseline_plan), *render_args, "--output-dir", str(baseline))
    _run_cli("render", str(combo_plan), *render_args, "--output-dir", str(combo))
    fit_only = _run_cli("verify", str(baseline), "--engine", "origin")
    verified = _run_cli("verify", str(combo), "--engine", "origin")
    assert fit_only["status"] == verified["status"] == "ok"
    assert verified["checks"] == {"native_fit": True, "artifact_reopened": True, "native_error": True}
    native = verified["readback"]["fit"]
    assert native["scatter_plot_count"] == 3
    assert native["error"]["column"] == "Y_SD"
    assert native["error"]["direction"] == "y"
    assert native["error"]["symmetric"] is True
    assert native["unweighted_numeric_check"] is True
    _assert_fit_unchanged(fit_only["readback"]["fit"]["result"], native["result"])
    for suffix in ("opju", "png", "pdf", "tif"):
        assert (combo / f"result.{suffix}").stat().st_size > 0
