"""Backend-neutral fit semantics for future XY render composition."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from .models import EngineError

FIT_ERRORS = frozenset(
    {
        "unsupported_fit_model",
        "unsupported_multi_series_fit",
        "unsupported_fit_range",
        "unsupported_fit_range_mode",
        "invalid_fit_range",
        "insufficient_fit_points",
        "fit_range_apply_failed",
        "fit_range_readback_failed",
        "fit_range_mismatch",
        "unsupported_fit_weighting",
        "unsupported_fit_parameter_policy",
        "native_fit_not_supported",
        "fit_create_failed",
        "fit_execution_failed",
        "fit_readback_failed",
        "fit_result_invalid",
        "fit_source_binding_failed",
        "fit_verify_failed",
        "native_fit_relationship_lost",
    }
)
RESULT_SOURCES = frozenset({"backend_native", "core_computed", "imported"})
WEIGHT_MODES = frozenset({"none", "inverse_y", "inverse_y2", "inverse_sigma", "inverse_sigma2", "column"})


@dataclass(frozen=True)
class ParameterSpec:
    mode: str = "free"
    value: float | None = None
    initial: float | None = None
    lower: float | None = None
    upper: float | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"free", "fixed"} or (self.mode == "fixed") != (self.value is not None):
            raise ValueError("A parameter must be free or fixed with a value")
        for value in (self.value, self.initial, self.lower, self.upper):
            if value is not None and not math.isfinite(value):
                raise ValueError("Parameter values must be finite")
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValueError("Parameter lower bound exceeds upper bound")


@dataclass(frozen=True)
class FitSpec:
    model: str
    x_column: str
    y_column: str
    parameters: dict[str, ParameterSpec] = field(
        default_factory=lambda: {
            "intercept": ParameterSpec(),
            "slope": ParameterSpec(),
        }
    )
    fit_range: tuple[float, float] | None = None
    weight_mode: str = "none"
    weight_column: str | None = None
    result_source: str = "backend_native"
    requested_statistics: tuple[str, ...] = ("r_squared",)
    curve_points: int = 100

    def __post_init__(self) -> None:
        if self.model != "linear":
            raise EngineError("unsupported_fit_model", f"Unsupported fit model: {self.model}")
        if not self.x_column or not self.y_column or self.x_column == self.y_column:
            raise ValueError("Fit requires distinct nonempty X and Y columns")
        if set(self.parameters) != {"intercept", "slope"}:
            raise ValueError("Linear fit parameters must be intercept and slope")
        if self.weight_mode not in WEIGHT_MODES:
            raise EngineError("unsupported_fit_weighting", f"Unsupported weight mode: {self.weight_mode}")
        if (self.weight_mode == "column") != (self.weight_column is not None):
            raise ValueError("Weight column is required only for column weighting")
        if self.fit_range is not None:
            try:
                valid_range = (
                    len(self.fit_range) == 2
                    and all(isinstance(v, (int, float)) and math.isfinite(v) for v in self.fit_range)
                    and self.fit_range[0] < self.fit_range[1]
                )
            except TypeError:
                valid_range = False
            if not valid_range:
                raise EngineError("invalid_fit_range", "Fit range needs finite increasing X bounds")
        if self.result_source not in RESULT_SOURCES:
            raise ValueError("Unknown fit result source")
        if not self.requested_statistics or any(not item for item in self.requested_statistics):
            raise ValueError("Requested statistics cannot be empty")
        if self.curve_points < 2:
            raise ValueError("Fit curve needs at least two points")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> FitSpec:
        data = dict(payload)
        if "parameters" in data:
            data["parameters"] = {name: ParameterSpec(**item) for name, item in data["parameters"].items()}
        if data.get("fit_range") is not None:
            if isinstance(data["fit_range"], dict):
                raise EngineError("unsupported_fit_range_mode", "Use a closed [min_x, max_x] interval")
            data["fit_range"] = tuple(data["fit_range"])
        if "requested_statistics" in data:
            data["requested_statistics"] = tuple(data["requested_statistics"])
        return cls(**data)


@dataclass(frozen=True)
class FitResult:
    model: str
    parameters: dict[str, float]
    statistics: dict[str, float]
    n_points: int
    fit_range: tuple[float, float] | None
    weight_mode: str
    backend: str
    result_source: str

    def __post_init__(self) -> None:
        if self.model != "linear" or set(self.parameters) != {"intercept", "slope"}:
            raise EngineError("fit_result_invalid", "Linear fit result has invalid model or parameters")
        if "r_squared" not in self.statistics or self.n_points < 2:
            raise EngineError("fit_result_invalid", "Fit result lacks R-squared or enough points")
        if any(not math.isfinite(v) for v in (*self.parameters.values(), *self.statistics.values())):
            raise EngineError("fit_result_invalid", "Fit result contains nonfinite numbers")
        if self.fit_range is not None and (
            len(self.fit_range) != 2
            or not all(math.isfinite(v) for v in self.fit_range)
            or self.fit_range[0] >= self.fit_range[1]
        ):
            raise EngineError("fit_range_readback_failed", "Native Fit range is invalid")
        if (
            self.result_source not in RESULT_SOURCES
            or self.weight_mode not in WEIGHT_MODES
            or not self.backend
        ):
            raise EngineError("fit_result_invalid", "Fit result provenance is invalid")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FitCapabilities:
    native_linear: bool
    editable: bool
    reopen: bool
    parameters_readback: bool
    r_squared_readback: bool

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


def fit_error(code: str, *, engine: str, cause: Exception | None = None) -> EngineError:
    if code not in FIT_ERRORS:
        raise ValueError(f"Unknown fit error code: {code}")
    return EngineError(
        code,
        f"{engine} fit failed at {code}.",
        engine=engine,
        cause_type=type(cause).__name__ if cause else None,
    )


def selected_fit_points(frame: Any, spec: FitSpec) -> Any:
    """Return finite X/Y pairs within the inclusive scientific X interval."""
    import numpy as np
    import pandas as pd

    pairs = frame[[spec.x_column, spec.y_column]].apply(pd.to_numeric, errors="coerce")
    pairs = pairs[pairs.notna().all(axis=1)]
    pairs = pairs[np.isfinite(pairs.to_numpy()).all(axis=1)]
    if spec.fit_range is not None:
        lower, upper = spec.fit_range
        pairs = pairs[pairs[spec.x_column].between(lower, upper, inclusive="both")]
    if len(pairs) < 2 or pairs[spec.x_column].nunique() < 2:
        raise EngineError("insufficient_fit_points", "Fit interval needs two distinct valid X values")
    return pairs


def production_linear_fit(plan: dict[str, Any]) -> FitSpec | None:
    """Validate the single-series native Fit scope before any desktop application starts."""
    payload = plan.get("fit")
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise EngineError("unsupported_fit_model", "FitSpec must be an object")
    try:
        spec = FitSpec.from_dict(payload)
    except EngineError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise EngineError("fit_result_invalid", "FitSpec is malformed") from exc
    render = plan.get("render_spec") or {}
    data = render.get("data") or {}
    if plan.get("template", {}).get("id") != "scatter" or render.get("chart_type") != "xy_scatter":
        raise EngineError("native_fit_not_supported", "Native linear Fit currently requires XY Scatter")
    y_columns = data.get("y")
    if not isinstance(y_columns, list) or len(y_columns) != 1:
        raise EngineError("unsupported_multi_series_fit", "Native linear Fit requires one Y series")
    if spec.x_column != data.get("x") or spec.y_column != y_columns[0]:
        raise EngineError("fit_source_binding_failed", "FitSpec columns differ from the scatter plan")
    errors = data.get("y_errors") or {}
    if errors and (
        not isinstance(errors, dict)
        or set(errors) != {spec.y_column}
        or not isinstance(errors[spec.y_column], dict)
        or errors[spec.y_column].get("kind") != "sd"
        or errors[spec.y_column].get("direction") != "y"
        or errors[spec.y_column].get("symmetric") is not True
        or not isinstance(errors[spec.y_column].get("column"), str)
        or errors[spec.y_column]["column"] in {"", spec.x_column, spec.y_column}
    ):
        raise EngineError("native_fit_not_supported", "Only one symmetric Y SD error is supported with Fit")
    if spec.weight_mode != "none":
        raise EngineError("unsupported_fit_weighting", "Weighted Fit is not supported")
    if any(parameter != ParameterSpec() for parameter in spec.parameters.values()):
        raise EngineError("unsupported_fit_parameter_policy", "Only free parameters are supported")
    if spec.result_source != "backend_native":
        raise EngineError("native_fit_not_supported", "This route requires backend-native fitting")
    if spec.requested_statistics != ("r_squared",):
        raise EngineError("native_fit_not_supported", "Only R-squared is available in this Fit route")
    return spec
