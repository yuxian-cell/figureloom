"""Independent native fits on existing multi-series XY line routes."""

from __future__ import annotations

import json
import os
import statistics
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "runtime" / "src", ROOT / "skill" / "figureloom" / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import figureloom_core as core  # noqa: E402
from figureloom_engine.fit_contract import FitSpec, production_linear_fits  # noqa: E402
from figureloom_engine.models import EngineError  # noqa: E402


def _plan(tmp_path: Path) -> Path:
    source = tmp_path / "independent.csv"
    source.write_text(
        "X,Control,Treatment\n1,2.1,4.2\n2,4.0,7.0\n3,6.2,10.1\n4,8.1,13.3\n5,9.9,15.9\n",
        encoding="ascii",
    )
    mapping = {"assignments": {"X": "x", "Control": "series", "Treatment": "series"}}
    understanding = core.understand_data(
        source, template_id="trend", mapping=mapping, engine_home=ROOT / "runtime"
    )
    specs = [
        FitSpec(model="linear", x_column="X", y_column=column).to_dict()
        for column in ("Control", "Treatment")
    ]
    plan = core.build_plan(
        source,
        template_id="trend",
        claim="Control and Treatment rise independently with X.",
        evidence_role="trend",
        mapping=mapping,
        semantic_confirmation=understanding["confirmation_gate"]["confirmation_payload_template"],
        fit_spec=specs,
        engine_home=ROOT / "runtime",
    )
    path = tmp_path / "render-plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_independent_fit_plan_keeps_series_order_and_rejects_weight(tmp_path: Path) -> None:
    plan = json.loads(_plan(tmp_path).read_text(encoding="utf-8"))
    assert [spec.y_column for spec in production_linear_fits(plan)] == ["Control", "Treatment"]
    assert plan["render_spec"]["data"]["y"] == ["Control", "Treatment"]
    plan["fit"][1]["weight_mode"] = "column"
    plan["fit"][1]["weight_column"] = "W"
    plan["fit"][1]["weight_interpretation"] = "direct_weight"
    with pytest.raises(EngineError) as error:
        production_linear_fits(plan)
    assert error.value.code == "unsupported_fit_weighting"
    plan["fit"][1].update(weight_mode="none", weight_column=None, weight_interpretation=None)
    plan["fit"][1]["fit_range"] = [2, 4]
    with pytest.raises(EngineError) as error:
        production_linear_fits(plan)
    assert error.value.code == "unsupported_fit_range"
    plan["fit"][1]["fit_range"] = None
    plan["fit"].reverse()
    with pytest.raises(EngineError) as error:
        production_linear_fits(plan)
    assert error.value.code == "fit_source_binding_failed"


def _assert_native_results(fits: dict, backend: str) -> None:
    x = [1, 2, 3, 4, 5]
    for column, y in {
        "Control": [2.1, 4.0, 6.2, 8.1, 9.9],
        "Treatment": [4.2, 7.0, 10.1, 13.3, 15.9],
    }.items():
        result = fits[column]["result"]
        expected = statistics.linear_regression(x, y)
        assert result["parameters"] == pytest.approx(
            {"slope": expected.slope, "intercept": expected.intercept}, abs=1e-6
        )
        assert result["statistics"]["r_squared"] == pytest.approx(
            statistics.correlation(x, y) ** 2, abs=1e-6
        )
        assert result["n_points"] == 5
        assert result["fit_range"] is None
        assert result["weight_mode"] == "none"
        assert result["result_source"] == "backend_native"
        assert result["backend"] == backend


@pytest.mark.grapher
@pytest.mark.skipif(os.name != "nt", reason="Grapher COM requires Windows")
def test_grapher_independent_native_fits(tmp_path: Path) -> None:
    pytest.importorskip("pythoncom")
    from grapher_sciplot.engine import GrapherEngine
    from grapher_sciplot.smoke import SmokeFailure, discover

    try:
        discover()
    except SmokeFailure as exc:
        pytest.skip(str(exc))
    plan_file = _plan(tmp_path)
    output = tmp_path / "grapher"
    engine = GrapherEngine()
    rendered = engine.render(
        json.loads(plan_file.read_text(encoding="utf-8")), plan_file=plan_file, output_dir=output
    )
    verified = engine.verify(output)
    assert rendered.status == verified["status"] == "ok"
    fits = verified["readback"]["fits"]
    assert set(fits) == {"Control", "Treatment"}
    _assert_native_results(fits, "grapher")
    assert (
        fits["Control"]["result"]["parameters"]["slope"]
        != fits["Treatment"]["result"]["parameters"]["slope"]
    )


@pytest.mark.origin
@pytest.mark.skipif(os.name != "nt", reason="Origin automation requires Windows")
def test_origin_independent_native_fits(tmp_path: Path) -> None:
    pytest.importorskip("originpro")
    if not core.discover_origin_application()["launch_registration_detected"]:
        pytest.skip("Origin isolated COM registration is unavailable")
    from figureloom_engine.origin import OriginEngine

    plan_file = _plan(tmp_path)
    output = tmp_path / "origin"
    engine = OriginEngine()
    rendered = engine.render(
        json.loads(plan_file.read_text(encoding="utf-8")), plan_file=plan_file,
        engine_home=ROOT / "runtime", python_executable=sys.executable, output_dir=output,
    )
    verified = engine.verify(output)
    assert rendered.status == verified["status"] == "ok"
    fits = verified["readback"]["fits"]
    assert set(fits) == {"Control", "Treatment"}
    _assert_native_results(fits, "origin")
    assert fits["Control"]["report_sheet"] != fits["Treatment"]["report_sheet"]
    assert fits["Control"]["curve_sheet"] != fits["Treatment"]["curve_sheet"]
    assert '"Control"' in fits["Control"]["operation_binding"]["y"]
    assert '"Treatment"' in fits["Treatment"]["operation_binding"]["y"]
    assert (
        fits["Control"]["operation_binding"]["plot_uid"]
        != fits["Treatment"]["operation_binding"]["plot_uid"]
    )
    assert (
        fits["Control"]["result"]["parameters"]["slope"]
        != fits["Treatment"]["result"]["parameters"]["slope"]
    )
