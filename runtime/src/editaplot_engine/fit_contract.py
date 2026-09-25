"""Backend-neutral fit semantics for future XY render composition."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from .models import EngineError

FIT_ERRORS = frozenset(
    {
        "unsupported_fit_model",
        "unsupported_fit_weighting",
        "native_fit_not_supported",
        "fit_create_failed",
        "fit_execution_failed",
        "fit_readback_failed",
        "fit_result_invalid",
        "fit_source_binding_failed",
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
        if self.fit_range is not None and (
            len(self.fit_range) != 2
            or not all(math.isfinite(v) for v in self.fit_range)
            or self.fit_range[0] >= self.fit_range[1]
        ):
            raise ValueError("Fit range must contain increasing finite X bounds")
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
