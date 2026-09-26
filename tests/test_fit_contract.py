from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "src"))

from editaplot_engine.fit_contract import (
    FitCapabilities,
    FitResult,
    FitSpec,
    ParameterSpec,
    fit_error,
)
from editaplot_engine.models import EngineError


def test_fit_spec_roundtrip_and_parameter_identity():
    spec = FitSpec(model="linear", x_column="X", y_column="Y")
    assert set(spec.parameters) == {"intercept", "slope"}
    assert spec.fit_range is None and spec.weight_mode == "none"
    assert FitSpec.from_dict(spec.to_dict()) == spec
    assert FitSpec.from_dict({**spec.to_dict(), "fit_range": [2, 4]}).fit_range == (2, 4)


def test_fit_spec_rejects_invalid_semantics():
    with pytest.raises(EngineError, match="Unsupported fit model") as error:
        FitSpec(model="polynomial", x_column="X", y_column="Y")
    assert error.value.code == "unsupported_fit_model"
    with pytest.raises(EngineError) as error:
        FitSpec(model="linear", x_column="X", y_column="Y", weight_mode="mystery")
    assert error.value.code == "unsupported_fit_weighting"
    with pytest.raises(ValueError):
        FitSpec(model="linear", x_column="X", y_column="Y", result_source="unknown")
    with pytest.raises(EngineError) as error:
        FitSpec(model="linear", x_column="X", y_column="Y", fit_range=(4, 2))
    assert error.value.code == "invalid_fit_range"
    with pytest.raises(ValueError):
        ParameterSpec(mode="fixed")
    with pytest.raises(ValueError):
        ParameterSpec(lower=2, upper=1)


def test_fit_result_provenance_and_finite_values():
    result = FitResult(
        "linear",
        {"intercept": 0.15, "slope": 1.97},
        {"r_squared": 0.99889324},
        5,
        None,
        "none",
        "grapher",
        "backend_native",
    )
    assert result.to_dict()["result_source"] == "backend_native"
    with pytest.raises(EngineError) as error:
        FitResult(
            "linear",
            {"intercept": 0.15, "slope": math.nan},
            {"r_squared": 0.99},
            5,
            None,
            "none",
            "origin",
            "backend_native",
        )
    assert error.value.code == "fit_result_invalid"
    with pytest.raises(EngineError) as error:
        FitResult(
            "linear", {"intercept": 0.15, "slope": 1.97},
            {"r_squared": 0.99}, 5, None, "none", "origin", "unknown",
        )
    assert error.value.code == "fit_result_invalid"


def test_capability_and_error_report():
    assert FitCapabilities(True, True, True, True, True).to_dict()["native_linear"]
    assert (
        fit_error("fit_readback_failed", engine="grapher", cause=RuntimeError()).to_dict()["error"]["code"]
        == "fit_readback_failed"
    )
    with pytest.raises(ValueError):
        fit_error("unlisted", engine="grapher")
