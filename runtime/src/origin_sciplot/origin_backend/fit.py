"""Attach native Origin LinearFit analysis to an existing Scatter OPJU."""

from __future__ import annotations

import json
import math
import shutil
import tempfile
from pathlib import Path
from typing import Any

from editaplot_engine.fit_contract import FitResult, FitSpec
from editaplot_engine.models import EngineError

from .export_utils import export_graph
from .session import OriginSession


def _source_sheet(op: Any, spec: FitSpec) -> tuple[Any, int, int]:
    for book in op.pages("w"):
        for sheet in book:
            columns = list(sheet.to_df().columns)
            if spec.x_column in columns and spec.y_column in columns:
                return sheet, columns.index(spec.x_column), columns.index(spec.y_column)
    raise EngineError("fit_source_binding_failed", "Origin source columns are missing", engine="origin")


def _read_saved_fit(op: Any, report_ref: str, curve_ref: str, spec: FitSpec) -> dict[str, Any]:
    report = op.find_sheet("w", report_ref)
    curve = op.find_sheet("w", curve_ref)
    graph = next(op.pages("g"), None)
    source, x_index, y_index = _source_sheet(op, spec)
    if report is None or curve is None or graph is None:
        raise EngineError(
            "native_fit_relationship_lost", "Origin saved analysis is incomplete", engine="origin"
        )
    columns = [report.to_list(i) for i in range(report.shape[1])]
    try:
        model = str(columns[2][3])
        source_x = str(columns[3][0])
        source_y = str(columns[4][0])
        range_text = str(columns[5][0])
        intercept, slope = float(columns[8][0]), float(columns[8][1])
        n_points, r_squared = int(columns[12][0]), float(columns[12][4])
    except (IndexError, TypeError, ValueError) as exc:
        raise EngineError(
            "fit_readback_failed", "Origin native report lacks linear Fit results", engine="origin"
        ) from exc
    if model != "y = a + b*x" or not all(math.isfinite(v) for v in (intercept, slope, r_squared)):
        raise EngineError("fit_result_invalid", "Origin native linear Fit result is invalid", engine="origin")
    if (
        f'"{spec.x_column}"' not in source_x
        or f'"{spec.y_column}"' not in source_y
        or len(graph[0].plot_list()) < 2
        or not curve.to_list(0)
        or not curve.to_list(1)
        or n_points < 2
    ):
        raise EngineError("native_fit_relationship_lost", "Origin Fit lost source or curve", engine="origin")
    result = FitResult(
        model="linear",
        parameters={"intercept": intercept, "slope": slope},
        statistics={"r_squared": r_squared},
        n_points=n_points,
        fit_range=None,
        weight_mode="none",
        backend="origin",
        result_source="backend_native",
    )
    return {
        "present": True,
        "native_editable": True,
        "object_type": "FitLinear analysis",
        "report_sheet": report_ref,
        "curve_sheet": curve_ref,
        "curve_present": True,
        "scatter_present": True,
        "scatter_plot_count": len(graph[0].plot_list()),
        "source_x_column": spec.x_column,
        "source_y_column": spec.y_column,
        "source_x_binding": source_x,
        "source_y_binding": source_y,
        "source_x_index": x_index,
        "source_y_index": y_index,
        "source_sheet": source.name,
        "fit_range_native": range_text,
        "full_range": range_text == f"[1*:{len(source.to_df())}*]",
        "weighting_readback": "unsupported",
        "result": result.to_dict(),
    }


def apply_linear_fit(output_dir: Path, spec: FitSpec) -> dict[str, Any]:
    opju = output_dir / "result.opju"
    with OriginSession(keep_open=False) as session:
        op = session.op
        if not op.open(str(opju), asksave=False):
            raise EngineError("fit_create_failed", "Origin could not reopen Scatter OPJU", engine="origin")
        source, x_index, y_index = _source_sheet(op, spec)
        graph = next(op.pages("g"), None)
        if graph is None or len(graph[0].plot_list()) != 1:
            raise EngineError(
                "fit_source_binding_failed", "Expected one native Scatter plot", engine="origin"
            )
        try:
            fit = op.LinearFit()
            fit.set_data(source, x_index, y_index)
            report_ref, curve_ref = fit.report()
            del fit
            curve = op.find_sheet("w", curve_ref)
            if curve is None:
                raise RuntimeError("Origin Fit curve worksheet is missing")
            graph[0].add_plot(curve, 1, 0, type="l")
            graph[0].rescale()
            if not op.save(str(opju)):
                raise RuntimeError("Origin could not save fitted OPJU")
            export_graph(
                op, graph, output_dir / "result.png", output_dir / "result.pdf", output_dir / "result.tif"
            )
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError(
                "fit_execution_failed", "Origin native LinearFit failed", engine="origin"
            ) from exc
        op.new(asksave=False)
        if not op.open(str(opju), asksave=False):
            raise EngineError("fit_readback_failed", "Origin fitted OPJU cannot reopen", engine="origin")
        readback = _read_saved_fit(op, report_ref, curve_ref, spec)
        readback["engine_version"] = session.environment.origin_version
    (output_dir / "origin_fit_readback.json").write_text(
        json.dumps(readback, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return readback


def verify_linear_fit(output_dir: Path, spec: FitSpec, report_ref: str, curve_ref: str) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(suffix=".opju", dir=output_dir, delete=False) as temporary:
        copy = Path(temporary.name)
    try:
        shutil.copy2(output_dir / "result.opju", copy)
        with OriginSession(keep_open=False) as session:
            op = session.op
            if not op.open(str(copy), asksave=False):
                raise EngineError("fit_readback_failed", "Origin fitted OPJU cannot reopen", engine="origin")
            readback = _read_saved_fit(op, report_ref, curve_ref, spec)
            op.new(asksave=False)
            return readback
    finally:
        copy.unlink(missing_ok=True)
