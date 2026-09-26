"""Attach native Origin LinearFit analysis to an existing Scatter OPJU."""

from __future__ import annotations

import json
import math
import re
import shutil
import statistics
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from editaplot_engine.fit_contract import (
    FitResult,
    FitSpec,
    selected_fit_points,
    selected_weighted_points,
)
from editaplot_engine.models import EngineError

from .export_utils import export_graph
from .session import OriginSession


def _main_graph(op: Any) -> Any:
    graphs = list(op.pages("g"))
    figures = [graph for graph in graphs if not graph.name.startswith(("FitLine", "Residual"))]
    return max(figures or graphs, key=lambda graph: len(graph[0].plot_list()), default=None)


def _source_sheet(op: Any, spec: FitSpec) -> tuple[Any, int, int]:
    graph = _main_graph(op)
    plotted = {plot.name for plot in graph[0].plot_list()} if graph is not None else set()
    for book in op.pages("w"):
        for sheet in book:
            columns = list(sheet.to_df().columns)
            if (
                spec.x_column in columns and spec.y_column in columns
                and (not plotted or _dataset_name(sheet, columns.index(spec.y_column)) in plotted)
            ):
                return sheet, columns.index(spec.x_column), columns.index(spec.y_column)
    raise EngineError("fit_source_binding_failed", "Origin source columns are missing", engine="origin")


def _dataset_name(source: Any, column_index: int) -> str:
    index = column_index + 1
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{source.get_book().name}_{letters}"


def _fit_source(op: Any, source: Any, spec: FitSpec) -> tuple[Any, str | None, tuple[int, int] | None]:
    if spec.weight_mode == "column":
        helper = op.new_sheet("w", lname="EditaPlot Fit Weights")
        helper.from_df(selected_weighted_points(source.to_df(), spec).reset_index(drop=True))
        return helper, f"[{helper.get_book().name}]{helper.name}", None
    if spec.fit_range is None:
        return source, None, None
    full = selected_fit_points(source.to_df(), replace(spec, fit_range=None))
    selected = selected_fit_points(source.to_df(), spec)
    full = full.sort_values(spec.x_column, kind="stable").reset_index(drop=True)
    lower, upper = spec.fit_range
    first = int((full[spec.x_column] < lower).sum()) + 1
    last = int((full[spec.x_column] <= upper).sum())
    if last - first + 1 != len(selected):
        raise EngineError(
            "fit_range_apply_failed", "Origin X interval mapping is inconsistent", engine="origin"
        )
    helper = op.new_sheet("w", lname="EditaPlot Fit Range")
    helper_frame = full.copy()
    helper_frame["FitMinX"] = [lower, *([float("nan")] * (len(full) - 1))]
    helper_frame["FitMaxX"] = [upper, *([float("nan")] * (len(full) - 1))]
    helper.from_df(helper_frame)
    return helper, f"[{helper.get_book().name}]{helper.name}", (first, last)


def _read_saved_fit(
    op: Any, report_ref: str, curve_ref: str, spec: FitSpec,
    error_column: str | None = None, fit_source_ref: str | None = None,
    *, multi_series: bool = False,
) -> dict[str, Any]:
    report = op.find_sheet("w", report_ref)
    curve = op.find_sheet("w", curve_ref)
    graph = _main_graph(op) if multi_series else next(op.pages("g"), None)
    source, x_index, y_index = _source_sheet(op, spec)
    if report is None or curve is None or graph is None:
        raise EngineError(
            "native_fit_relationship_lost", "Origin saved analysis is incomplete", engine="origin"
        )
    columns = [report.to_list(i) for i in range(report.shape[1])]
    try:
        offset = int(error_column is not None or spec.weight_mode == "column")
        model = str(columns[2][3])
        source_x = str(columns[3][0])
        source_y = str(columns[4][0])
        range_text = str(columns[5][0])
        source_weight = str(columns[6][0]) if spec.weight_mode == "column" else None
        intercept, slope = float(columns[8 + offset][0]), float(columns[8 + offset][1])
        n_points, r_squared = int(columns[12 + offset][0]), float(columns[12 + offset][4])
    except (IndexError, TypeError, ValueError) as exc:
        raise EngineError(
            "fit_readback_failed", "Origin native report lacks linear Fit results", engine="origin"
        ) from exc
    if model != "y = a + b*x" or not all(math.isfinite(v) for v in (intercept, slope, r_squared)):
        raise EngineError("fit_result_invalid", "Origin native linear Fit result is invalid", engine="origin")
    plot_names = [plot.name for plot in graph[0].plot_list()]
    scatter_present = _dataset_name(source, y_index) in plot_names
    operation_binding = None
    if multi_series:
        if not op.lt_exec(f"op_change ir:={report_ref} tr:=ED_FIT_OPERATION;"):
            raise EngineError("fit_readback_failed", "Origin analysis operation is missing", engine="origin")
        try:
            operation = op.lt_tree_to_dict("ED_FIT_OPERATION", add_attributes=True)
            native_input = operation["GUI"]["InputData"]["Range1"]
            native_uid = int(operation["GUI"]["InputData"]["___Range1"]["PlotObjUID"])
            target = next(
                plot for plot in graph[0].plot_list()
                if plot.name == _dataset_name(source, y_index)
            )
            expected_uid = op.lt_int(f"range2uid({target.lt_range()})")
            operation_binding = {
                "x": native_input["X"], "y": native_input["Y"],
                "plot_uid": native_uid,
            }
        except (KeyError, TypeError, ValueError, StopIteration) as exc:
            raise EngineError(
                "fit_readback_failed", "Origin analysis operation input is incomplete", engine="origin"
            ) from exc
        finally:
            op.lt_exec("del -vt ED_FIT_OPERATION;")
        if (
            f'"{spec.x_column}"' not in operation_binding["x"]
            or f'"{spec.y_column}"' not in operation_binding["y"]
            or native_uid != expected_uid
        ):
            raise EngineError(
                "fit_source_binding_failed", "Origin analysis lock targets the wrong XY plot",
                engine="origin",
            )
    source_frame = source.to_df()
    weighted_points = None
    if spec.weight_mode == "column":
        if spec.weight_column not in source_frame:
            raise EngineError("weight_readback_failed", "Origin saved W column is missing", engine="origin")
        weighted_points = selected_weighted_points(source_frame, spec)
        if f'"{spec.weight_column}"' not in (source_weight or ""):
            raise EngineError("weight_binding_failed", "Origin Fit no longer binds to W", engine="origin")
    native_range: tuple[float, float] | None = None
    if fit_source_ref is not None and spec.fit_range is not None:
        helper = op.find_sheet("w", fit_source_ref)
        match = re.fullmatch(r"\[(\d+):(\d+)\]", range_text)
        if helper is None or match is None:
            raise EngineError("fit_range_readback_failed", "Origin native range is missing", engine="origin")
        helper_frame = helper.to_df()
        first, last = int(match[1]), int(match[2])
        if not (1 <= first < last <= len(helper_frame)):
            raise EngineError(
                "fit_range_readback_failed", "Origin native row range is invalid", engine="origin"
            )
        if not all(f"[{helper.get_book().name}]" in binding for binding in (source_x, source_y)):
            raise EngineError(
                "fit_range_mismatch", "Origin Fit no longer binds to its helper data", engine="origin"
            )
        full = selected_fit_points(source_frame, replace(spec, fit_range=None))
        sorted_full = full.sort_values(spec.x_column, kind="stable").reset_index(drop=True)
        if not helper_frame[[spec.x_column, spec.y_column]].equals(sorted_full):
            raise EngineError(
                "fit_range_mismatch", "Origin helper data differ from Scatter source", engine="origin"
            )
        stored = (float(helper_frame["FitMinX"].iloc[0]), float(helper_frame["FitMaxX"].iloc[0]))
        expected_first = int((sorted_full[spec.x_column] < stored[0]).sum()) + 1
        expected_last = int((sorted_full[spec.x_column] <= stored[1]).sum())
        native_range = stored if (first, last) == (expected_first, expected_last) else (
            float(sorted_full[spec.x_column].iloc[first - 1]),
            float(sorted_full[spec.x_column].iloc[last - 1]),
        )
    if fit_source_ref is not None and spec.weight_mode == "column":
        helper = op.find_sheet("w", fit_source_ref)
        if helper is None or weighted_points is None:
            raise EngineError(
                "weight_readback_failed", "Origin weighted Fit helper is missing", engine="origin"
            )
        expected = weighted_points[[spec.x_column, spec.y_column, spec.weight_column]].reset_index(drop=True)
        helper_frame = helper.to_df()
        if not set(expected.columns).issubset(helper_frame):
            raise EngineError(
                "weight_readback_failed", "Origin weighted Fit helper lacks source columns", engine="origin"
            )
        if not helper_frame[list(expected.columns)].equals(expected):
            raise EngineError(
                "weight_verify_mismatch", "Origin Fit helper differs from source", engine="origin"
            )
        if not all(
            f"[{helper.get_book().name}]" in binding
            for binding in (source_x, source_y, source_weight or "")
        ):
            raise EngineError(
                "weight_binding_failed", "Origin Fit is not bound to weight helper", engine="origin"
            )
    if error_column and error_column not in source_frame:
        raise EngineError("native_fit_relationship_lost", "Origin error column is missing", engine="origin")
    error_index = list(source_frame.columns).index(error_column) if error_column else None
    error_present = error_index is not None and _dataset_name(source, error_index) in plot_names
    if (
        f'"{spec.x_column}"' not in source_x
        or f'"{spec.y_column}"' not in source_y
        or not scatter_present
        or len(plot_names) < 2 + (error_column is not None)
        or (error_column is not None and not error_present)
        or not curve.to_list(0)
        or not curve.to_list(1)
        or n_points < 2
    ):
        raise EngineError("native_fit_relationship_lost", "Origin Fit lost source or curve", engine="origin")
    if error_column is not None or fit_source_ref is not None or spec.weight_mode == "column":
        try:
            if weighted_points is not None:
                selected = weighted_points
                x, y, w = (
                    selected[column].to_numpy(dtype=float)
                    for column in (spec.x_column, spec.y_column, spec.weight_column)
                )
                weight_total = w.sum()
                x_mean, y_mean = (w @ x) / weight_total, (w @ y) / weight_total
                expected_slope = (w @ ((x - x_mean) * (y - y_mean))) / (w @ ((x - x_mean) ** 2))
                expected_intercept = y_mean - expected_slope * x_mean
                expected_r_squared = 1 - (w @ ((y - expected_intercept - expected_slope * x) ** 2)) / (
                    w @ ((y - y_mean) ** 2)
                )
            else:
                selected = selected_fit_points(source_frame, spec)
                expected = statistics.linear_regression(
                    selected[spec.x_column], selected[spec.y_column]
                )
                expected_slope, expected_intercept = expected.slope, expected.intercept
                expected_r_squared = statistics.correlation(
                    selected[spec.x_column], selected[spec.y_column]
                ) ** 2
        except (TypeError, ValueError, statistics.StatisticsError) as exc:
            raise EngineError(
                "fit_result_invalid", "Origin Fit source data are invalid", engine="origin"
            ) from exc
        if (
            n_points != len(selected)
            or not math.isclose(slope, expected_slope, rel_tol=1e-6, abs_tol=1e-8)
            or not math.isclose(intercept, expected_intercept, rel_tol=1e-6, abs_tol=1e-8)
            or not math.isclose(r_squared, expected_r_squared, rel_tol=1e-6, abs_tol=1e-8)
        ):
            raise EngineError(
                "weight_verify_mismatch" if weighted_points is not None else "fit_result_invalid",
                "Origin Fit differs from the specified X/Y/weight data", engine="origin"
            )
    result = FitResult(
        model="linear",
        parameters={"intercept": intercept, "slope": slope},
        statistics={"r_squared": r_squared},
        n_points=n_points,
        fit_range=native_range,
        weight_mode=spec.weight_mode,
        backend="origin",
        result_source="backend_native",
        weight_column=spec.weight_column,
        weight_interpretation=spec.weight_interpretation,
    )
    return {
        "present": True,
        "native_editable": True,
        "object_type": "FitLinear analysis",
        "report_sheet": report_ref,
        "curve_sheet": curve_ref,
        "curve_present": True,
        "scatter_present": scatter_present,
        "scatter_n_points": len(source_frame),
        "scatter_plot_count": len(plot_names),
        "scatter_dataset": _dataset_name(source, y_index),
        "error": {
            "present": error_present,
            "column": error_column,
            "column_index": error_index,
            "dataset": _dataset_name(source, error_index) if error_index is not None else None,
            "direction": "y" if error_present else None,
            "symmetric": error_present,
        },
        "source_x_column": spec.x_column,
        "source_y_column": spec.y_column,
        "source_x_binding": source_x,
        "source_y_binding": source_y,
        "operation_binding": operation_binding,
        "source_weight_binding": source_weight,
        "weighting_readback_source": (
            "native_report_binding_and_numeric_direct_wls" if weighted_points is not None else None
        ),
        "source_x_index": x_index,
        "source_y_index": y_index,
        "source_sheet": source.name,
        "fit_source_ref": fit_source_ref,
        "fit_range_native": range_text,
        "full_range": range_text == f"[1*:{len(source.to_df())}*]",
        "weighting_readback": (
            "direct_weight_verified" if weighted_points is not None else "unsupported"
        ),
        "unweighted_numeric_check": (
            spec.weight_mode == "none" and (error_column is not None or fit_source_ref is not None)
        ),
        "result": result.to_dict(),
    }


def apply_linear_fit(
    output_dir: Path, spec: FitSpec, error_column: str | None = None, *, allow_existing: bool = False
) -> dict[str, Any]:
    opju = output_dir / "result.opju"
    with OriginSession(keep_open=False) as session:
        op = session.op
        if not op.open(str(opju), asksave=False):
            raise EngineError("fit_create_failed", "Origin could not reopen Scatter OPJU", engine="origin")
        source, x_index, y_index = _source_sheet(op, spec)
        graph = _main_graph(op)
        if graph is None or (
            not allow_existing and len(graph[0].plot_list()) != 1 + (error_column is not None)
        ):
            raise EngineError(
                "fit_source_binding_failed", "Expected native Scatter and optional error plot",
                engine="origin",
            )
        try:
            fit_source, fit_source_ref, rows = _fit_source(op, source, spec)
            fit = op.LinearFit()
            fit_x, fit_y = (0, 1) if fit_source_ref is not None else (x_index, y_index)
            fit.set_data(fit_source, fit_x, fit_y, spec.weight_column or "")
            if allow_existing:
                target = next(
                    plot for plot in graph[0].plot_list()
                    if plot.name == _dataset_name(source, y_index)
                )
                uid = op.lt_int(f"range2uid({target.lt_range()})")
                if uid <= 0:
                    raise EngineError(
                        "fit_source_binding_failed", "Origin could not bind Fit to XY plot",
                        engine="origin",
                    )
                op.lt_exec(
                    f'{fit._get_tree_name()}.GUI.InputData.Range1.SetAttribute("PlotObjUID", {uid});'
                )
                native_input = op.lt_tree_to_dict(fit._get_tree_name(), add_attributes=True)
                if int(native_input["GUI"]["InputData"]["___Range1"]["PlotObjUID"]) != uid:
                    raise EngineError(
                        "fit_source_binding_failed", "Origin Fit ignored XY plot binding",
                        engine="origin",
                    )
            if rows is not None:
                try:
                    for label, index in (("X", 0), ("Y", 1)):
                        fit._set(
                            f"InputData.Range1.{label}$",
                            f"{fit_source.to_col_range(index)}[{rows[0]}:{rows[1]}]",
                        )
                except Exception as exc:
                    raise EngineError(
                        "fit_range_apply_failed", "Origin could not set native input range",
                        engine="origin",
                    ) from exc
            # Origin's Direct Weighting mode uses the ED source as direct W.
            # An unweighted Fit must explicitly turn off Origin's automatic Y-error weighting.
            fit._set("Fit.ErrBarWeight", 1 if spec.weight_mode == "column" else 0)
            report_ref, curve_ref = fit.report()
            op.lt_exec("xop execute:=cleanup;")
            del fit
            curve = op.find_sheet("w", curve_ref)
            if curve is None:
                raise RuntimeError("Origin Fit curve worksheet is missing")
            if not allow_existing:
                graph[0].add_plot(curve, 1, 0, type="l")
            graph[0].rescale()
            if error_column is not None:
                legend = graph[0].label("legend")
                if legend is not None:
                    # Origin rebuilds the linked legend after Fit.report(),
                    # adding duplicate fit entries. The fit report labels the
                    # curve, so remove that misleading automatic legend.
                    legend.remove()
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
        readback = _read_saved_fit(
            op, report_ref, curve_ref, spec, error_column, fit_source_ref,
            multi_series=allow_existing,
        )
        readback["engine_version"] = session.environment.origin_version
    (output_dir / "origin_fit_readback.json").write_text(
        json.dumps(readback, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return readback


def verify_linear_fit(
    output_dir: Path, spec: FitSpec, report_ref: str, curve_ref: str,
    error_column: str | None = None, fit_source_ref: str | None = None,
    *, multi_series: bool = False,
) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(suffix=".opju", dir=output_dir, delete=False) as temporary:
        copy = Path(temporary.name)
    try:
        shutil.copy2(output_dir / "result.opju", copy)
        with OriginSession(keep_open=False) as session:
            op = session.op
            if not op.open(str(copy), asksave=False):
                raise EngineError("fit_readback_failed", "Origin fitted OPJU cannot reopen", engine="origin")
            readback = _read_saved_fit(
                op, report_ref, curve_ref, spec, error_column, fit_source_ref,
                multi_series=multi_series,
            )
            op.new(asksave=False)
            return readback
    finally:
        copy.unlink(missing_ok=True)
