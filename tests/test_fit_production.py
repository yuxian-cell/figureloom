from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "src"))

from editaplot_engine.fit_contract import (  # noqa: E402
    FitSpec,
    ParameterSpec,
    production_linear_fit,
    selected_fit_points,
)
from editaplot_engine.models import EngineError  # noqa: E402
from grapher_sciplot.fit import parse_statistics  # noqa: E402


def _plan() -> dict:
    return {
        "template": {"id": "scatter"},
        "render_spec": {"chart_type": "xy_scatter", "data": {"x": "X", "y": ["Y"]}},
        "fit": FitSpec(model="linear", x_column="X", y_column="Y").to_dict(),
    }


def test_linear_fit_dispatch_and_scope():
    plan = _plan()
    assert production_linear_fit(plan).result_source == "backend_native"
    plan["fit"]["fit_range"] = [2, 4]
    assert production_linear_fit(plan).fit_range == (2, 4)
    plan["render_spec"]["data"]["y_errors"] = {
        "Y": {"column": "Y_SD", "kind": "sd", "direction": "y", "symmetric": True}
    }
    assert production_linear_fit(plan).weight_mode == "none"
    del plan["fit"]
    assert production_linear_fit(plan) is None


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (lambda p: p["render_spec"]["data"].update(y=["Y", "Z"]), "unsupported_multi_series_fit"),
        (lambda p: p["fit"].update(fit_range=[4, 2]), "invalid_fit_range"),
        (lambda p: p["fit"].update(fit_range={"mode": "row_interval"}), "unsupported_fit_range_mode"),
        (lambda p: p["fit"].update(weight_mode="inverse_y2"), "unsupported_fit_weighting"),
        (
            lambda p: p["fit"]["parameters"].update(intercept=vars(ParameterSpec(mode="fixed", value=0))),
            "unsupported_fit_parameter_policy",
        ),
        (lambda p: p["fit"].update(result_source="core_computed"), "native_fit_not_supported"),
        (lambda p: p["fit"].update(y_column="Z"), "fit_source_binding_failed"),
        (
            lambda p: p["render_spec"]["data"].update(y_errors={"Y": {"column": "SD", "kind": "ci"}}),
            "native_fit_not_supported",
        ),
        (
            lambda p: p["render_spec"]["data"].update(y_errors={"Y": {
                "column": "Y_SD", "kind": "sd", "direction": "y", "symmetric": False,
            }}),
            "native_fit_not_supported",
        ),
        (
            lambda p: p["fit"].update(requested_statistics=["r_squared", "p_value"]),
            "native_fit_not_supported",
        ),
    ],
)
def test_unsupported_fit_requests_fail_before_com(change, code):
    plan = _plan()
    change(plan)
    with pytest.raises(EngineError) as error:
        production_linear_fit(plan)
    assert error.value.code == code


def test_grapher_native_statistics_normalization():
    text = (
        "Equation Y = 1.97 * X + 0.15\n"
        "Number of data points used = 5\n"
        "Coefficient of determination, R-sq'd = 0.99889324"
    )
    assert parse_statistics(text) == (1.97, 0.15, 0.99889324, 5)
    assert parse_statistics(text.replace("1.97 * X + 0.15", "-1.97E-2 * X - 1.5E-1")) == (
        -0.0197, -0.15, 0.99889324, 5,
    )


def test_inclusive_fit_range_and_insufficient_points():
    import pandas as pd

    frame = pd.DataFrame({"X": [1, 2, 3, 4, 5], "Y": [2, 4, 6, 8, 10]})
    spec = FitSpec(model="linear", x_column="X", y_column="Y", fit_range=(2, 4))
    assert selected_fit_points(frame, spec)["X"].tolist() == [2, 3, 4]
    with pytest.raises(EngineError) as error:
        selected_fit_points(frame, FitSpec(model="linear", x_column="X", y_column="Y", fit_range=(4.1, 4.9)))
    assert error.value.code == "insufficient_fit_points"


@pytest.mark.parametrize("bounds", [(2, 2), (4, 2), (math.nan, 4), (1, math.inf)])
def test_invalid_fit_range_has_stable_error(bounds):
    with pytest.raises(EngineError) as error:
        FitSpec(model="linear", x_column="X", y_column="Y", fit_range=bounds)
    assert error.value.code == "invalid_fit_range"


def test_fit_range_skips_missing_values_and_preserves_input_order():
    import pandas as pd

    frame = pd.DataFrame({"X": [5, 2, 4, 1, 3], "Y": [10, 4, float("nan"), 2, 6]})
    spec = FitSpec(model="linear", x_column="X", y_column="Y", fit_range=(2, 5))
    assert selected_fit_points(frame, spec)["X"].tolist() == [5, 2, 3]
