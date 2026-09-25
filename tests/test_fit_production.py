from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "src"))

from editaplot_engine.fit_contract import FitSpec, ParameterSpec, production_linear_fit  # noqa: E402
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
    del plan["fit"]
    assert production_linear_fit(plan) is None


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (lambda p: p["render_spec"]["data"].update(y=["Y", "Z"]), "unsupported_multi_series_fit"),
        (lambda p: p["fit"].update(fit_range=[2, 4]), "unsupported_fit_range"),
        (lambda p: p["fit"].update(weight_mode="inverse_y2"), "unsupported_fit_weighting"),
        (
            lambda p: p["fit"]["parameters"].update(intercept=vars(ParameterSpec(mode="fixed", value=0))),
            "unsupported_fit_parameter_policy",
        ),
        (lambda p: p["fit"].update(result_source="core_computed"), "native_fit_not_supported"),
        (lambda p: p["fit"].update(y_column="Z"), "fit_source_binding_failed"),
        (
            lambda p: p["render_spec"]["data"].update(y_errors={"Y": {"column": "SD"}}),
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
