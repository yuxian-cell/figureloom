"""Quadratic FitSpec and native Origin/Grapher integration."""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "runtime" / "src", ROOT / "skill" / "editaplot" / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import editaplot_core as core  # noqa: E402
from editaplot_engine.fit_contract import FitResult, FitSpec, production_linear_fits  # noqa: E402
from editaplot_engine.models import EngineError  # noqa: E402
from grapher_sciplot.fit import parse_polynomial_statistics  # noqa: E402


def _plan(tmp_path: Path, *, model: str = "polynomial") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "quadratic.csv"
    source.write_text("X,Y\n-2,9\n-1,4\n0,1\n1,0\n2,1\n3,4\n", encoding="ascii")
    mapping = {"assignments": {"X": "x", "Y": "series"}}
    understanding = core.understand_data(
        source, template_id="scatter", mapping=mapping, engine_home=ROOT / "runtime"
    )
    plan = core.build_plan(
        source, template_id="scatter", claim="Y follows a quadratic relationship with X.",
        evidence_role="relationship", mapping=mapping,
        semantic_confirmation=understanding["confirmation_gate"]["confirmation_payload_template"],
        fit_spec=FitSpec(
            model=model, degree=2 if model == "polynomial" else None, x_column="X", y_column="Y"
        ).to_dict(),
        engine_home=ROOT / "runtime",
    )
    path = tmp_path / "render-plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_quadratic_contract_and_scope(tmp_path: Path) -> None:
    spec = FitSpec(model="polynomial", degree=2, x_column="X", y_column="Y")
    assert FitSpec.from_dict(spec.to_dict()) == spec
    assert set(spec.parameters) == {"a0", "a1", "a2"}
    assert FitResult("polynomial", {"a0": 1, "a1": -2, "a2": 1},
                     {"r_squared": 1}, 6, None, "none", "origin", "backend_native",
                     degree=2).to_dict()["degree"] == 2
    assert "degree" not in FitSpec(model="linear", x_column="X", y_column="Y").to_dict()
    plan = json.loads(_plan(tmp_path).read_text(encoding="utf-8"))
    assert production_linear_fits(plan) == (spec,)
    for degree, code in ((None, "invalid_fit_degree"), (2.0, "invalid_fit_degree"),
                         ("2", "invalid_fit_degree"), (True, "invalid_fit_degree"),
                         (-1, "unsupported_polynomial_degree"), (0, "unsupported_polynomial_degree"),
                         (3, "unsupported_polynomial_degree")):
        with pytest.raises(EngineError) as error:
            FitSpec(model="polynomial", degree=degree, x_column="X", y_column="Y")
        assert error.value.code == code
    for changes, code in (({"fit_range": (0, 2)}, "unsupported_fit_range"),
                          ({"weight_mode": "inverse_y"}, "unsupported_fit_weighting")):
        with pytest.raises(EngineError) as error:
            FitSpec(model="polynomial", degree=2, x_column="X", y_column="Y", **changes)
        assert error.value.code == code
    plan["fit"] = [spec.to_dict(), spec.to_dict()]
    with pytest.raises(EngineError) as error:
        production_linear_fits(plan)
    assert error.value.code == "unsupported_multi_series_fit"
    plan["fit"] = spec.to_dict()
    plan["render_spec"]["data"]["y_errors"] = {"Y": {"column": "Y_SD"}}
    with pytest.raises(EngineError) as error:
        production_linear_fits(plan)
    assert error.value.code == "native_fit_not_supported"


def test_grapher_quadratic_statistics_normalization() -> None:
    text = "\n".join(("Degree = 2", "Number of data points used = 6",
                      "Degree 0 = 1", "Degree 1 = -2", "Degree 2 = 1",
                      "Coefficient of determination, R-sq'd = 0",
                      "Coefficient of determination, R-sq'd = 0.31914894",
                      "Coefficient of determination, R-sq'd = 1"))
    assert parse_polynomial_statistics(text) == ({"a0": 1, "a1": -2, "a2": 1}, 1, 6)


def _assert_native(result: dict, backend: str) -> None:
    assert result["model"] == "polynomial"
    assert result["degree"] == 2
    assert result["parameters"] == pytest.approx({"a0": 1, "a1": -2, "a2": 1}, abs=1e-6)
    assert math.isclose(result["statistics"]["r_squared"], 1, abs_tol=1e-6)
    assert result["n_points"] == 6
    assert result["fit_range"] is None
    assert result["weight_mode"] == "none"
    assert result["result_source"] == "backend_native"
    assert result["backend"] == backend


@pytest.mark.origin
@pytest.mark.skipif(os.name != "nt", reason="Origin automation requires Windows")
def test_origin_native_quadratic_fit(tmp_path: Path) -> None:
    pytest.importorskip("originpro")
    if not core.discover_origin_application()["launch_registration_detected"]:
        pytest.skip("Origin isolated COM registration is unavailable")
    from editaplot_engine.origin import OriginEngine

    plan_file = _plan(tmp_path)
    output = tmp_path / "origin"
    engine = OriginEngine()
    rendered = engine.render(
        json.loads(plan_file.read_text(encoding="utf-8")), plan_file=plan_file,
        engine_home=ROOT / "runtime", python_executable=sys.executable, output_dir=output,
    )
    verified = engine.verify(output)
    assert rendered.status == verified["status"] == "ok"
    native = verified["readback"]["fit"]
    _assert_native(native["result"], "origin")
    assert native["native_degree"] == 2
    assert '"Y"' in native["operation_binding"]["y"]
    for suffix in ("opju", "png", "pdf", "tif"):
        assert (output / f"result.{suffix}").is_file()
    assert native["result"]["statistics"]["r_squared"] > 0.99


@pytest.mark.grapher
@pytest.mark.skipif(os.name != "nt", reason="Grapher COM requires Windows")
def test_grapher_native_quadratic_fit(tmp_path: Path) -> None:
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
    native = verified["readback"]["fit"]
    _assert_native(native["result"], "grapher")
    assert native["native_fit_type"] == 5 and native["native_degree"] == 2
    for suffix in ("grf", "png", "pdf"):
        assert (output / f"result.{suffix}").is_file()
    assert native["result"]["statistics"]["r_squared"] > 0.99
