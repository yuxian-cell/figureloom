"""Native Fit capability attached to an existing Grapher XY plot."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from figureloom_engine.fit_contract import FitResult, FitSpec
from figureloom_engine.models import EngineError

from .smoke import call, get, put


def add_fit(plot: Any, spec: FitSpec) -> Any:
    try:
        fit = call(plot, "AddFit", 0 if spec.model == "linear" else 5)
        if spec.model == "polynomial":
            put(fit, "Degree", spec.degree)
        put(get(fit, "line"), "width", 0.025)
    except Exception as exc:
        raise EngineError(
            "fit_create_failed", f"Grapher could not add native {spec.model} Fit", engine="grapher"
        ) from exc
    if spec.fit_range is not None:
        try:
            put(fit, "UseCurveLimits", False)
            put(fit, "MinX", float(spec.fit_range[0]))
            put(fit, "MaxX", float(spec.fit_range[1]))
        except Exception as exc:
            raise EngineError(
                "fit_range_apply_failed", "Grapher could not set native X limits", engine="grapher"
            ) from exc
    return fit


def _native_statistics(document: Any, fit: Any) -> str:
    """Read a linked native Fit text object through Grapher's SVG export."""
    shapes = get(document, "Shapes")
    before = int(get(shapes, "Count"))
    call(fit, "InsertStatistics", 1.0, 1.0)
    if int(get(shapes, "Count")) != before + 1:
        raise EngineError("fit_readback_failed", "Grapher did not insert Fit statistics", engine="grapher")
    shape = call(shapes, "Item", before + 1)
    try:
        if (
            int(get(shape, "Type")) != 6
            or int(get(get(shape, "FitPlot"), "fitType")) != int(get(fit, "fitType"))
        ):
            raise EngineError(
                "fit_readback_failed", "Statistics text is not linked to native Fit", engine="grapher"
            )
        with tempfile.TemporaryDirectory(prefix="figureloom-fit-") as directory:
            svg = Path(directory) / "fit-statistics.svg"
            if not call(document, "Export", str(svg)) or not svg.is_file():
                raise EngineError(
                    "fit_readback_failed", "Grapher could not export native Fit text", engine="grapher"
                )
            root = ElementTree.parse(svg).getroot()  # noqa: S314 - Grapher just generated this file
            lines = [
                "".join(node.itertext()) for node in root.iter() if node.tag.endswith("}text")
            ]
            if "Fit Results" not in lines:
                raise EngineError("fit_readback_failed", "Grapher SVG lacks Fit report", engine="grapher")
            text = "\n".join(lines[lines.index("Fit Results"):])
            if "Equation Y =" not in text or "R-sq'd =" not in text:
                raise EngineError(
                    "fit_readback_failed", "Grapher SVG lacks native Fit statistics", engine="grapher"
                )
            return text
    finally:
        call(shape, "Delete")


def parse_statistics(text: str) -> tuple[float, float, float, int]:
    number = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
    equation = re.search(rf"Equation Y = ({number}) \* X ([+-]) ({number})", text)
    r_squared = re.search(rf"Coefficient of determination, R-sq'd = ({number})", text)
    n_points = re.search(r"Number of data points used = (\d+)", text)
    if not equation or not r_squared or not n_points:
        raise EngineError("fit_readback_failed", "Grapher native statistics are incomplete", engine="grapher")
    return (
        float(equation.group(1)),
        float(equation.group(3)) * (1 if equation.group(2) == "+" else -1),
        float(r_squared.group(1)),
        int(n_points.group(1)),
    )


def parse_polynomial_statistics(text: str) -> tuple[dict[str, float], float, int]:
    number = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
    degree = re.search(r"^Degree = (\d+)$", text, re.MULTILINE)
    points = re.search(r"Number of data points used = (\d+)", text)
    coefficients = dict(re.findall(rf"^Degree ([012]) = ({number})$", text, re.MULTILINE))
    r_squared = re.findall(rf"Coefficient of determination, R-sq'd = ({number})", text)
    if (
        not degree or degree.group(1) != "2" or not points
        or set(coefficients) != {"0", "1", "2"} or len(r_squared) < 3
    ):
        raise EngineError(
            "fit_readback_failed", "Grapher polynomial statistics are incomplete", engine="grapher"
        )
    return ({f"a{index}": float(coefficients[str(index)]) for index in range(3)},
            float(r_squared[-1]), int(points.group(1)))


def read_fit(plot: Any, document: Any) -> dict[str, Any] | None:
    fits = get(plot, "Fits")
    if int(get(fits, "Count")) == 0:
        return None
    if int(get(fits, "Count")) != 1:
        raise EngineError("fit_readback_failed", "Expected one native Fit", engine="grapher")
    fit = call(fits, "Item", 1)
    fit_type = int(get(fit, "fitType"))
    if fit_type not in {0, 5}:
        raise EngineError("fit_readback_failed", "Native Fit model is unsupported", engine="grapher")
    try:
        statistics_text = _native_statistics(document, fit)
        if fit_type == 0:
            slope, intercept, r_squared, n_points = parse_statistics(statistics_text)
            parameters = {"intercept": intercept, "slope": slope}
            degree = None
        else:
            degree = int(get(fit, "Degree"))
            if degree != 2:
                raise EngineError(
                    "fit_readback_failed", "Grapher polynomial degree changed", engine="grapher"
                )
            parameters, r_squared, n_points = parse_polynomial_statistics(statistics_text)
        minimum, maximum = float(get(fit, "MinX")), float(get(fit, "MaxX"))
        full_range = bool(get(fit, "UseCurveLimits"))
        fit_range = None if full_range else (minimum, maximum)
        result = FitResult(
            model="linear" if fit_type == 0 else "polynomial",
            degree=degree,
            parameters=parameters,
            statistics={"r_squared": r_squared},
            n_points=n_points,
            fit_range=fit_range,
            weight_mode="none",
            backend="grapher",
            result_source="backend_native",
        )
        return {
            "present": True,
            "native_editable": True,
            "object_type": "AutoFitPlot",
            "native_fit_type": fit_type,
            "native_degree": degree,
            "name": str(get(fit, "Name")),
            "source_x_column_index": int(get(plot, "xCol")),
            "source_y_column_index": int(get(plot, "yCol")),
            "source_worksheet": str(get(plot, "worksheet")),
            "fit_min_x": minimum,
            "fit_max_x": maximum,
            "full_range": full_range,
            "weighting_readback": "unsupported",
            "statistics_readback_source": "native_linked_text_svg",
            "curve_present": True,
            "result": result.to_dict(),
        }
    except EngineError:
        raise
    except Exception as exc:
        raise EngineError("fit_readback_failed", "Grapher Fit readback failed", engine="grapher") from exc
