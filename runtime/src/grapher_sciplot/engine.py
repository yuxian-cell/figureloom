"""Native Grapher XY scatter and line routes for FigureLoom RenderPlans."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import re
import shutil
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from figureloom_engine.fit_contract import (
    FIT_CAPABILITIES,
    FitSpec,
    production_linear_fits,
    selected_fit_points,
)
from figureloom_engine.models import EngineError, RenderResult

from .error_bar import add_y_error, read_y_error
from .fit import add_fit, read_fit
from .smoke import (
    application as _application,
)
from .smoke import (
    call,
    discover,
    get,
    open_document,
    put,
    require_file,
    run_smoke,
)

_DEFAULT_COLORS = ("#1F6F78", "#C86B3C", "#6A5D98", "#5E8D4E")
SUPPORTED_TEMPLATE_ROUTES = ("scatter", "trend", "line_error", "bar", "cv", "lsv", "xas")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _default_output_dir(source: Path) -> Path:
    label = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", source.stem).strip(" ._") or "data"
    return source.parent / f"{label}_FigureLoom_{datetime.now():%Y%m%d_%H%M%S}"


def _claim_output(path: Path) -> Path:
    for candidate in (path, *(path.with_name(f"{path.name}_{index:02d}") for index in range(2, 1000))):
        try:
            candidate.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return candidate
    raise EngineError(
        "output_directory_name_exhausted",
        "FigureLoom could not allocate a unique delivery-folder name.",
        engine="grapher",
    )


def _color_value(value: str) -> int:
    text = value.lstrip("#")
    red, green, blue = (int(text[index : index + 2], 16) for index in (0, 2, 4))
    return red | (green << 8) | (blue << 16)


def _read_source(plan: dict[str, Any]) -> pd.DataFrame:
    source = Path(plan["source"]["path"])
    if source.suffix.casefold() in {".xlsx", ".xls"}:
        return pd.read_excel(source, sheet_name=plan["source"].get("sheet") or 0)
    if source.suffix.casefold() in {".csv", ".txt"}:
        error: Exception | None = None
        for encoding in ("utf-8-sig", "utf-16", "gb18030"):
            try:
                return pd.read_csv(source, sep=None, engine="python", encoding=encoding)
            except UnicodeError as exc:
                error = exc
        if error is not None:
            raise error
    raise ValueError(f"Unsupported source format: {source.suffix}")



def _optional_get(obj: Any, name: str) -> Any | None:
    try:
        return get(obj, name)
    except Exception:
        return None


def _plot_mode(symbol_frequency: int, line_style: str) -> str:
    if line_style.casefold() != "invisible":
        return "xy_line"
    return "xy_scatter" if symbol_frequency > 0 else "unknown"


def _visual_mode(chart_type: str, style: dict[str, Any]) -> tuple[int, float]:
    if chart_type == "xy_scatter":
        return 1, 0.0
    return (
        1 if style.get("show_symbols") else 0,
        max(0.005, float(style.get("line_width_pt") or 1.5) / 72.0),
    )


class GrapherEngine:
    name = "grapher"

    def detect(self) -> dict[str, Any]:
        registration = discover()
        version = None
        if importlib.util.find_spec("win32api") is not None:
            import win32api

            info = win32api.GetFileVersionInfo(registration["executable"], "\\")
            most, least = info["FileVersionMS"], info["FileVersionLS"]
            version = ".".join(
                str(value) for value in (most >> 16, most & 0xFFFF, least >> 16, least & 0xFFFF)
            )
        return {**registration, "version": version}

    def doctor(self, *, engine_home: str | Path | None = None) -> dict[str, Any]:
        del engine_home
        from figureloom_engine.correlation_heatmap import HEATMAP_CAPABILITIES
        try:
            detection = self.detect()
            try:
                for module in ("pythoncom", "win32api", "win32com.client"):
                    __import__(module)
                automation_available = True
            except ImportError:
                automation_available = False
            return {
                "status": "ok" if automation_available else "failed",
                "engine": self.name,
                "installed": True,
                "automation_available": automation_available,
                "connection_policy": "attach_or_own",
                "missing_dependencies": [] if automation_available else ["pywin32==312"],
                "version": detection["version"],
                "progid": detection["progid"],
                "executable": detection["executable"],
                "ready_for_analysis": True,
                "ready_for_render": automation_available,
                "fit_capabilities": FIT_CAPABILITIES[self.name].to_dict(),
                "heatmap_capabilities": HEATMAP_CAPABILITIES[self.name],
            }
        except Exception as exc:
            code = getattr(exc, "code", "grapher_not_installed")
            return {
                "status": "failed",
                "engine": self.name,
                "installed": False,
                "automation_available": False,
                "version": None,
                "ready_for_analysis": True,
                "ready_for_render": False,
                "fit_capabilities": FIT_CAPABILITIES[self.name].to_dict(),
                "heatmap_capabilities": HEATMAP_CAPABILITIES[self.name],
                "error": {"code": code, "message": str(exc)},
            }

    def smoke(
        self,
        output_dir: str | Path,
        *,
        engine_home: str | Path | None = None,
        python_executable: str | Path | None = None,
        visible: bool = True,
        keep_application_open: bool = False,
    ) -> dict[str, Any]:
        del engine_home, python_executable, keep_application_open
        return run_smoke(Path(output_dir), visible=visible)

    @staticmethod
    def _prepare(plan: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
        render_spec = plan.get("render_spec")
        route = plan["template"]["id"]
        if route not in SUPPORTED_TEMPLATE_ROUTES or not isinstance(render_spec, dict):
            raise EngineError(
                "grapher_route_unsupported",
                "Grapher does not support this template route.",
                engine="grapher",
                supported_templates=list(SUPPORTED_TEMPLATE_ROUTES),
            )
        if plan.get("reference_adaptation") is not None or plan.get("reference_style") is not None:
            raise EngineError(
                "grapher_reference_style_unsupported",
                "The first Grapher route does not yet support reference-style adaptation.",
                engine="grapher",
            )
        data = render_spec.get("data")
        chart_type = render_spec.get("chart_type")
        is_bar = route == "bar"
        if (
            chart_type not in {"xy_scatter", "xy_line", "simple_bar", "grouped_bar"}
            or (route == "scatter") != (chart_type == "xy_scatter")
            or is_bar != (chart_type in {"simple_bar", "grouped_bar"})
            or not isinstance(data, dict)
        ):
            raise EngineError(
                "grapher_route_unsupported",
                "The Grapher chart type does not match its template route.",
                engine="grapher",
            )
        x_column = data.get("category") if is_bar else data.get("x")
        y_columns = data.get("y")
        if (
            not isinstance(x_column, str)
            or not isinstance(y_columns, list)
            or not y_columns
            or any(not isinstance(column, str) for column in y_columns)
            or (chart_type == "xy_scatter" and len(y_columns) != 1)
            or (chart_type == "simple_bar" and len(y_columns) != 1)
            or (chart_type == "grouped_bar" and len(y_columns) < 2)
        ):
            raise EngineError(
                "grapher_route_unsupported",
                "Grapher requires a category/X column and the series count required by this route.",
                engine="grapher",
            )
        y_errors = data.get("y_errors") or {}
        if not isinstance(y_errors, dict) or set(y_errors) - set(y_columns):
            raise EngineError(
                "grapher_errorbar_create_failed", "Invalid per-series error mapping.", engine="grapher"
            )
        error_columns: list[str] = []
        for y_column, error in y_errors.items():
            if not isinstance(error, dict):
                raise EngineError(
                    "grapher_errorbar_create_failed", f"Invalid error for {y_column}.", engine="grapher"
                )
            if error.get("direction") != "y":
                raise EngineError(
                    "unsupported_error_direction", "Only Y errors are supported.", engine="grapher"
                )
            if error.get("symmetric") is not True or any(
                key in error for key in ("negative_column", "positive_column", "lower_column", "upper_column")
            ):
                raise EngineError(
                    "unsupported_asymmetric_error", "Only symmetric errors are supported.", engine="grapher"
                )
            if error.get("kind") not in {"sd", "sem", "ci", "explicit"}:
                raise EngineError("unsupported_error_kind", "Unsupported error meaning.", engine="grapher")
            column = error.get("column")
            if not isinstance(column, str) or not column:
                raise EngineError(
                    "missing_error_column", f"No error column for {y_column}.", engine="grapher"
                )
            if column not in error_columns:
                error_columns.append(column)
        try:
            frame = _read_source(plan)
            missing = [column for column in error_columns if column not in frame]
            if missing:
                raise EngineError(
                    "missing_error_column", f"Error column {missing[0]!r} is missing.", engine="grapher"
                )
            if x_column not in frame:
                raise EngineError(
                    "invalid_category" if is_bar else "grapher_data_staging_failed",
                    f"Anchor column {x_column!r} is missing.",
                    engine="grapher",
                )
            missing_y = [column for column in y_columns if column not in frame]
            if missing_y:
                raise EngineError(
                    "missing_value_column", f"Value column {missing_y[0]!r} is missing.", engine="grapher"
                )
            selected = frame[[x_column, *y_columns, *error_columns]].copy()
            if is_bar and (
                bool(selected[x_column].isna().any())
                or bool(selected[x_column].astype(str).str.strip().eq("").any())
            ):
                raise EngineError("invalid_category", "Bar categories must be nonempty.", engine="grapher")
            for column in selected.columns[1:] if is_bar else selected.columns:
                try:
                    selected[column] = pd.to_numeric(selected[column], errors="raise")
                except (TypeError, ValueError) as exc:
                    code = (
                        "error_column_not_numeric"
                        if column in error_columns
                        else "value_column_not_numeric"
                        if is_bar
                        else "grapher_data_staging_failed"
                    )
                    raise EngineError(code, f"Column {column!r} must be numeric.", engine="grapher") from exc
            for y_column, error in y_errors.items():
                values = selected[error["column"]]
                plotted = selected[x_column].notna() & selected[y_column].notna()
                if bool(values[plotted].isna().any()):
                    raise EngineError(
                        "error_length_mismatch", f"Error data are missing for {y_column}.", engine="grapher"
                    )
                if bool((values[plotted] < 0).any()):
                    raise EngineError(
                        "negative_error", f"Error data are negative for {y_column}.", engine="grapher"
                    )
        except EngineError:
            raise
        except Exception as exc:
            raise EngineError("grapher_data_staging_failed", str(exc), engine="grapher") from exc
        return render_spec, selected

    @staticmethod
    def _readback_in_app(app: Any, artifact: Path) -> dict[str, Any]:
        document = None
        try:
            document = open_document(app, artifact)
            shapes = get(document, "Shapes")
            plots: list[dict[str, Any]] = []
            axes_payload: dict[str, Any] = {}
            legends_payload: list[dict[str, Any]] = []
            graph_title = ""
            graph_title_linked = False
            graph_count = 0
            fits_readback: dict[str, dict[str, Any]] = {}
            category_column: str | None = None
            category_labels: dict[str, Any] = {}
            for shape_index in range(1, int(get(shapes, "Count")) + 1):
                shape = call(shapes, "Item", shape_index)
                graph_plots = _optional_get(shape, "Plots")
                graph_axes = _optional_get(shape, "Axes")
                if graph_plots is None or graph_axes is None:
                    continue
                graph_count += 1
                graph_title = str(get(get(shape, "title"), "text"))
                graph_title_linked = bool(get(shape, "LinkTitleToObjectName"))
                for plot_index in range(1, int(get(graph_plots, "Count")) + 1):
                    plot = call(graph_plots, "Item", plot_index)
                    if _optional_get(plot, "fitType") is not None:
                        continue
                    bar_plot = _optional_get(plot, "Stacked") is not None
                    if not bar_plot:
                        native_fit = read_fit(plot, document)
                        if native_fit is not None:
                            fits_readback[str(get(plot, "Name"))] = native_fit
                    symbol_frequency = int(_optional_get(plot, "symbolFreq") or 0)
                    line = get(plot, "line")
                    line_width = float(_optional_get(line, "width") or 0.0)
                    line_style = str(get(line, "style"))
                    worksheet = str(get(plot, "worksheet"))
                    error = read_y_error(plot)
                    if error["present"]:
                        try:
                            with Path(worksheet).open(encoding="utf-8-sig", newline="") as stream:
                                columns = next(csv.reader(stream))
                            error["column"] = columns[error["column_index"] - 1]
                        except (OSError, IndexError, StopIteration) as exc:
                            raise EngineError(
                                "grapher_errorbar_readback_failed",
                                "Could not resolve native error-column assignment.",
                                engine="grapher",
                            ) from exc
                    if bar_plot:
                        with Path(worksheet).open(encoding="utf-8-sig", newline="") as stream:
                            category_column = next(csv.reader(stream))[0]
                    plots.append(
                        {
                            "type": "bar" if bar_plot else _plot_mode(symbol_frequency, line_style),
                            "name": str(get(plot, "Name")),
                            "x_column_index": int(get(plot, "xCol")),
                            "y_column_index": int(get(plot, "yCol")),
                            "worksheet": worksheet,
                            "error": error,
                            "symbol_frequency": symbol_frequency,
                            "line_width": line_width,
                            "line_enabled": line_style.casefold() != "invisible",
                            "line_style": line_style,
                            "line_color": int(get(line, "foreColor")),
                            "fill_color": int(get(get(plot, "Fill"), "foreColor")) if bar_plot else None,
                            "stacked": bool(get(plot, "Stacked")) if bar_plot else None,
                            "orientation": int(get(plot, "Orientation")) if bar_plot else None,
                            "object_type": int(get(plot, "Type")),
                        }
                    )
                graph_legends = get(shape, "Legends")
                for legend_index in range(1, int(get(graph_legends, "Count")) + 1):
                    legend = call(graph_legends, "Item", legend_index)
                    legends_payload.append(
                        {
                            "entries": [
                                str(call(legend, "EntryName", entry_index))
                                for entry_index in range(1, int(get(legend, "EntryCount")) + 1)
                            ]
                        }
                    )
                for axis_index, key in ((1, "x"), (2, "y")):
                    if int(get(graph_axes, "Count")) >= axis_index:
                        axis = call(graph_axes, "Item", axis_index)
                        title = get(axis, "title")
                        axes_payload[key] = {
                            "present": True,
                            "title": str(get(title, "text")),
                            "object_type": int(get(axis, "Type")),
                        }
                        if key == "x" and any(item["type"] == "bar" for item in plots):
                            ticks = get(axis, "TickLabels")
                            category_labels = {
                                "mode": int(get(ticks, "Mode")),
                                "data_column_index": int(get(ticks, "WorksheetDataCol")),
                                "label_column_index": int(get(ticks, "WorksheetLabelCol")),
                                "first_row": int(get(ticks, "FirstLabelRow")),
                                "worksheet": str(get(ticks, "worksheet")),
                            }
            result = {
                "engine": "grapher",
                "document": {"opened": True, "path": str(artifact)},
                "graph_count": graph_count,
                "series_count": len(plots),
                "chart_type": ("simple_bar" if len(plots) == 1 else "grouped_bar")
                if category_column
                else (plots[0]["type"] if plots else "unknown"),
                "category_column": category_column,
                "category_labels": category_labels,
                "graph_title": graph_title,
                "graph_title_linked_to_name": graph_title_linked,
                "plots": plots,
                "axes": axes_payload,
                "legends": legends_payload,
            }
            if len(fits_readback) == 1:
                result["fit"] = next(iter(fits_readback.values()))
            elif fits_readback:
                result["fits"] = fits_readback
            return result
        finally:
            if document is not None:
                call(document, "Close", False)
                document = None

    def readback(self, artifact: str | Path) -> dict[str, Any]:
        from figureloom_engine.correlation_runtime import is_correlation_project, readback

        if is_correlation_project(Path(artifact)):
            return readback(self.name, Path(artifact).resolve())
        path = Path(artifact).resolve()
        require_file(path, "grapher_readback_failed")
        with _application(visible=False) as (app, _metadata):
            return self._readback_in_app(app, path)

    def apply_edit(self, artifact: str | Path, edit: dict[str, str]) -> dict[str, Any]:
        """Change an existing GRF object and verify it after reopening the saved file."""
        path = Path(artifact).resolve()
        require_file(path, "artifact_not_found")
        operation = edit["operation"]
        document = None
        with _application(visible=False) as (app, _metadata):
            try:
                document = open_document(app, path)
                shapes = get(document, "Shapes")
                graph = next(
                    (shape for index in range(1, int(get(shapes, "Count")) + 1)
                     if (shape := call(shapes, "Item", index)) and _optional_get(shape, "Plots") is not None),
                    None,
                )
                if graph is None:
                    raise EngineError("edit_target_not_found", "No native graph exists.", engine=self.name)
                if operation == "set_axis_title":
                    axis_index = {"x": 1, "y": 2}[edit["axis"]]
                    axis = call(get(graph, "Axes"), "Item", axis_index)
                    put(get(axis, "title"), "text", edit["value"])
                elif operation == "set_line_style":
                    plots = get(graph, "Plots")
                    target = next(
                        (plot for index in range(1, int(get(plots, "Count")) + 1)
                         if (plot := call(plots, "Item", index))
                         and str(get(plot, "Name")) == edit["series"]),
                        None,
                    )
                    if target is None:
                        raise EngineError("edit_target_not_found", "Series was not found.", engine=self.name)
                    put(
                        get(target, "line"), "style",
                        {"solid": "Solid", "dashed": ".1 in. Dash"}[edit["value"]],
                    )
                else:
                    raise EngineError("edit_unsupported", "This edit is not supported.", engine=self.name)
                call(document, "SaveAs", str(path))
                call(document, "Export2", str(path.with_suffix(".png")), False, "Defaults=0", True, "png")
                call(
                    document, "Export2", str(path.with_suffix(".pdf")),
                    False, "Defaults=0, EmbedFonts=1", True, "pdfv",
                )
            finally:
                if document is not None:
                    call(document, "Close", False)
        native = self.readback(path)
        if operation == "set_axis_title":
            actual = native["axes"][edit["axis"]]["title"]
            expected = edit["value"]
            manifest_path = path.parent / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["expected"][f"{edit['axis']}_title"] = expected
            _write_json(manifest_path, manifest)
        else:
            target = next((plot for plot in native["plots"] if plot["name"] == edit["series"]), None)
            actual = target["line_style"] if target else None
            expected = {"solid": "Solid", "dashed": ".1 in. Dash"}[edit["value"]]
        if actual != expected:
            raise EngineError("edit_verify_failed", "Native edit did not persist.", engine=self.name)
        report = self.verify(path.parent)
        if report["status"] != "ok":
            raise EngineError(
                "edit_verify_failed", "Edited GRF failed native verification.", engine=self.name
            )
        return {"status": "ok", "engine": self.name, "operation": operation,
                "actual": actual, "readback": native, "verification": report["status"]}

    def render(
        self,
        plan: dict[str, Any],
        *,
        plan_file: str | Path,
        engine_home: str | Path | None = None,
        python_executable: str | Path | None = None,
        output_dir: str | Path | None = None,
        close_application: bool = False,
    ) -> RenderResult:
        del engine_home, python_executable, close_application
        import figureloom_core

        figureloom_core.validate_plan(plan)
        if plan.get("correlation_heatmap") is not None:
            from figureloom_engine.correlation_runtime import render

            return render(self.name, plan, plan_file, output_dir)
        fit_specs = production_linear_fits(plan)
        fit_spec = fit_specs[0] if len(fit_specs) == 1 else None
        if (
            fit_spec is not None
            and fit_spec.weight_mode == "column"
            and not FIT_CAPABILITIES[self.name].explicit_weight
        ):
            raise EngineError(
                "unsupported_fit_weighting",
                "Grapher native Linear Fit does not support explicit per-point direct weights",
                engine=self.name,
                requested_capability="explicit_weighted_linear_fit",
                native_support=False,
            )
        render_spec, frame = self._prepare(plan)
        if fit_spec is not None and fit_spec.fit_range is not None:
            selected_fit_points(frame, fit_spec)
        data = render_spec["data"]
        chart_type = render_spec["chart_type"]
        is_bar = chart_type in {"simple_bar", "grouped_bar"}
        x_column, y_columns = (data["category"] if is_bar else data["x"]), data["y"]
        y_errors = data.get("y_errors") or {}
        axes_spec = render_spec["axes"]
        style = render_spec.get("style") or {}
        size = render_spec.get("size_inches") or {}
        source = Path(plan["source"]["path"]).resolve()
        requested = Path(output_dir).expanduser().resolve() if output_dir else _default_output_dir(source)
        target = _claim_output(requested)
        input_copy = target / f"input_copy{source.suffix.lower()}"
        shutil.copy2(source, input_copy)
        shutil.copy2(Path(plan_file).resolve(), target / "render-plan.json")
        staging = target / "grapher_staging.csv"
        frame.to_csv(staging, index=False, encoding="utf-8-sig", lineterminator="\n")
        grf, png, pdf = (target / f"result.{suffix}" for suffix in ("grf", "png", "pdf"))
        colors = style.get("colors") or _DEFAULT_COLORS
        series_colors = [str(colors[index % len(colors)]) for index in range(len(y_columns))]
        document = graph = plot = None
        with _application(visible=True) as (app, application):
            try:
                document = call(get(app, "Documents"), "Add", 0)
                graph = call(
                    get(document, "Shapes"),
                    "AddBarChartGraph" if is_bar else "AddLinePlotGraph",
                    str(staging),
                    0 if is_bar else 1,
                    2,
                )
                put(graph, "width", float(size.get("width", 6.5)))
                put(graph, "height", float(size.get("height", 4.5)))
                for index, column in enumerate(y_columns):
                    plot = (
                        call(get(graph, "Plots"), "Item", 1)
                        if index == 0
                        else call(
                            graph,
                            "AddBarChart" if is_bar else "AddLinePlot",
                            str(staging),
                            0 if is_bar else 1,
                            frame.columns.get_loc(column) + 1,
                        )
                    )
                    put(plot, "Name", column)
                    put(plot, "xCol", 0 if is_bar else 1)
                    put(plot, "yCol", frame.columns.get_loc(column) + 1)
                    color = _color_value(series_colors[index])
                    if is_bar:
                        call(plot, "SetPlotType", 31)  # Grapher grfVBarChart.
                        put(plot, "Stacked", False)
                        put(get(plot, "Fill"), "foreColor", color)
                        put(get(plot, "line"), "foreColor", color)
                    else:
                        symbol_frequency, line_width = _visual_mode(chart_type, style)
                        put(plot, "symbolFreq", symbol_frequency)
                        if chart_type == "xy_scatter":
                            call(plot, "SetPlotType", 28)  # Grapher grfScatterPlot.
                        line = get(plot, "line")
                        if chart_type == "xy_line":
                            put(line, "width", line_width)
                        put(line, "foreColor", color)
                        symbol = get(plot, "symbol")
                        put(symbol, "size", max(0.06, float(style.get("marker_size_pt") or 7.0) / 72.0))
                        put(get(symbol, "Fill"), "foreColor", color)
                    if column in y_errors:
                        add_y_error(plot, frame.columns.get_loc(y_errors[column]["column"]) + 1, color=color)
                    if fit_specs:
                        add_fit(plot, fit_specs[index])
                if is_bar:
                    put(graph, "GroupsAdjacent", True)
                    labels = get(call(get(graph, "Axes"), "Item", 1), "TickLabels")
                    put(labels, "worksheet", str(staging))
                    put(labels, "WorksheetDataCol", 0)
                    put(labels, "WorksheetLabelCol", 1)
                    put(labels, "AutoFirstLabelRow", False)
                    put(labels, "FirstLabelRow", 2)
                    put(labels, "Mode", 2)  # Grapher grfLabelsWorksheet.
                if len(y_columns) > 1 or fit_specs:
                    call(graph, "AddLegend", True)
                axes = get(graph, "Axes")
                put(get(call(axes, "Item", 1), "title"), "text", axes_spec["x"]["title"])
                put(get(call(axes, "Item", 2), "title"), "text", axes_spec["y"]["title"])
                title = str(plan["figure_contract"].get("core_conclusion") or "FigureLoom")
                put(graph, "LinkTitleToObjectName", False)
                put(get(graph, "title"), "text", title)
                call(document, "SaveAs", str(grf))
                require_file(grf, "grapher_save_failed")
                call(document, "Export2", str(png), False, "Defaults=0", True, "png")
                call(document, "Export2", str(pdf), False, "Defaults=0, EmbedFonts=1", True, "pdfv")
                require_file(png, "grapher_export_failed")
                require_file(pdf, "grapher_export_failed")
            except EngineError:
                raise
            except Exception as exc:
                raise EngineError("grapher_render_failed", str(exc), engine=self.name) from exc
            finally:
                graph = plot = None
                if document is not None:
                    call(document, "Close", False)
                    document = None

        manifest = {
            "schema_version": "1.0",
            "engine": self.name,
            "engine_version": application["version"],
            "ownership": application["ownership"],
            "connection_mode": application["connection_mode"],
            "pid": application["pid"],
            "editable_format": "grf",
            "plan_hash": plan["plan_hash"],
            "source": {
                "path": str(source),
                "sha256": plan["source"]["sha256"],
                "copy": str(input_copy),
            },
            "staging": {
                "path": str(staging),
                "sha256": _sha256(staging),
                "columns": list(frame.columns),
            },
            "expected": {
                "chart_type": chart_type,
                "category_column" if is_bar else "x_column": x_column,
                "y_columns": y_columns,
                "y_errors": y_errors,
                **({"fit": fit_spec.to_dict()} if fit_spec else {}),
                **({"fits": [spec.to_dict() for spec in fit_specs]} if len(fit_specs) > 1 else {}),
                "colors": series_colors,
                "graph_title": title,
                "x_title": axes_spec["x"]["title"],
                "y_title": axes_spec["y"]["title"],
            },
        }
        _write_json(target / "manifest.json", manifest)
        report = self.verify(target)
        if report["status"] != "ok":
            raise EngineError(
                "grapher_verify_failed",
                "Grapher render artifacts failed verification.",
                engine=self.name,
                report=str(target / "grapher_verify_report.json"),
            )
        result = RenderResult(
            engine=self.name,
            status="ok",
            output_dir=target,
            editable_path=grf,
            exports={"png": png, "pdf": pdf},
            readback=report["readback"],
            metadata={
                "engine_version": application["version"],
                "ownership": application["ownership"],
                "connection_mode": application["connection_mode"],
                "pid": application["pid"],
                "editable_format": "grf",
                "manifest": str(target / "manifest.json"),
                "verify_report": str(target / "grapher_verify_report.json"),
                **({"fit": report["readback"]["fit"]["result"]} if fit_spec else {}),
                **({"fits": {name: item["result"] for name, item in report["readback"]["fits"].items()}}
                   if len(fit_specs) > 1 else {}),
            },
        )
        _write_json(target / "render-result.json", result.to_dict())
        return result

    def verify(self, output_dir: str | Path) -> dict[str, Any]:
        from figureloom_engine.correlation_runtime import is_correlation_project, verify

        if is_correlation_project(Path(output_dir) / "result.grf"):
            return verify(self.name, Path(output_dir).resolve())
        target = Path(output_dir).expanduser().resolve()
        manifest_path = target / "manifest.json"
        expected_files = {
            "editable": target / "result.grf",
            "png": target / "result.png",
            "pdf": target / "result.pdf",
            "manifest": manifest_path,
        }
        artifacts = {
            name: {
                "path": str(path),
                "exists": path.is_file(),
                "size_bytes": path.stat().st_size if path.is_file() else 0,
            }
            for name, path in expected_files.items()
        }
        files_ok = all(item["size_bytes"] > 0 for item in artifacts.values())
        signatures_ok = False
        readback: dict[str, Any] = {}
        bindings_ok = axes_ok = staging_ok = mode_ok = legend_ok = colors_ok = title_ok = False
        error_bindings_ok = False
        fit_ok = True
        is_bar = False
        error: dict[str, str] | None = None
        try:
            if not files_ok:
                raise EngineError("grapher_artifact_missing", "One or more Grapher artifacts are missing.")
            signatures_ok = (
                expected_files["editable"].read_bytes().startswith(b"Grapher")
                and expected_files["png"].read_bytes().startswith(b"\x89PNG")
                and expected_files["pdf"].read_bytes().startswith(b"%PDF")
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            expected = manifest["expected"]
            plan_copy = target / "render-plan.json"
            if plan_copy.is_file():
                planned_fit = json.loads(plan_copy.read_text(encoding="utf-8")).get("fit")
                if planned_fit != expected.get("fit", expected.get("fits")):
                    raise EngineError(
                        "fit_verify_failed", "Saved FitSpec differs from RenderPlan", engine="grapher"
                    )
            y_columns = expected.get("y_columns") or [expected["y_column"]]
            y_errors = expected.get("y_errors") or {}
            chart_type = expected["chart_type"]
            is_bar = chart_type in {"simple_bar", "grouped_bar"}
            anchor = expected["category_column"] if is_bar else expected["x_column"]
            staging_info = manifest["staging"]
            staging_path = Path(staging_info["path"]).resolve()
            staging_columns: list[str] = []
            if staging_path.is_file():
                with staging_path.open(encoding="utf-8-sig", newline="") as stream:
                    staging_columns = next(csv.reader(stream), [])
                staging_ok = _sha256(staging_path) == staging_info[
                    "sha256"
                ] and staging_columns == staging_info.get("columns", [anchor, *y_columns])
            readback = self.readback(expected_files["editable"])
            plots = readback.get("plots", [])
            bindings_ok = (
                readback.get("graph_count") == 1
                and len(plots) == len(y_columns)
                and all(
                    plot.get("x_column_index") == (0 if is_bar else 1)
                    and plot.get("y_column_index") == staging_columns.index(column) + 1
                    and Path(plot.get("worksheet", "")).resolve() == staging_path
                    and ("y_columns" not in expected or plot.get("name") == column)
                    for plot, column in zip(plots, y_columns, strict=True)
                )
            )
            if is_bar:
                labels = readback.get("category_labels", {})
                mode_ok = (
                    readback.get("chart_type") == chart_type
                    and readback.get("category_column") == anchor
                    and labels.get("mode") == 2
                    and labels.get("data_column_index") == 0
                    and labels.get("label_column_index") == 1
                    and labels.get("first_row") == 2
                    and Path(labels.get("worksheet", "")).resolve() == staging_path
                    and all(
                        plot.get("type") == "bar"
                        and plot.get("stacked") is False
                        and plot.get("orientation") == 0
                        for plot in plots
                    )
                )
            else:
                mode_ok = all(
                    plot.get("type") == chart_type
                    and bool(plot.get("line_enabled")) == (chart_type == "xy_line")
                    and (chart_type != "xy_scatter" or plot.get("symbol_frequency", 0) > 0)
                    for plot in plots
                ) and bool(plots)
            error_bindings_ok = len(plots) == len(y_columns) and all(
                (
                    plot.get("error", {}).get("present") is True
                    and plot["error"].get("column") == y_errors[column]["column"]
                    and plot["error"].get("column_index")
                    == staging_columns.index(y_errors[column]["column"]) + 1
                    and plot["error"].get("direction") == "y"
                    and plot["error"].get("symmetric") is True
                    and (
                        "colors" not in expected
                        or plot["error"].get("line_color")
                        == _color_value(expected["colors"][y_columns.index(column)])
                        and plot["error"].get("cap_color")
                        == _color_value(expected["colors"][y_columns.index(column)])
                    )
                )
                if column in y_errors
                else not plot.get("error", {}).get("present", False)
                for plot, column in zip(plots, y_columns, strict=True)
            )
            legend_ok = len(y_columns) == 1 or any(
                legend.get("entries") == y_columns for legend in readback.get("legends", [])
            )
            if "fits" in expected:
                wanted = {name for column in y_columns for name in (column, f"Linear Fit - {column}")}
                legend_ok = any(
                    wanted.issubset(legend.get("entries", [])) for legend in readback.get("legends", [])
                )
            colors_ok = "colors" not in expected or (
                len(plots) == len(expected["colors"])
                and all(
                    plot.get("fill_color" if is_bar else "line_color") == _color_value(color)
                    for plot, color in zip(plots, expected["colors"], strict=True)
                )
            )
            axes_ok = (
                readback.get("axes", {}).get("x", {}).get("title") == expected["x_title"]
                and readback.get("axes", {}).get("y", {}).get("title") == expected["y_title"]
            )
            title_ok = "graph_title" not in expected or (
                readback.get("graph_title") == expected["graph_title"]
                and readback.get("graph_title_linked_to_name") is False
            )
            if bindings_ok and staging_ok:
                for plot, column in zip(plots, y_columns, strict=True):
                    plot["category_column" if is_bar else "x_column"] = anchor
                    plot["y_column"] = column
            fit_ok = True
            if "fit" in expected:
                native_fit = readback.get("fit") or {}
                fit_result = native_fit.get("result") or {}
                fit_spec = FitSpec.from_dict(expected["fit"])
                fit_name = "Linear" if fit_spec.model == "linear" else "Polynomial"
                fit_legend = any(
                    legend.get("entries") == [y_columns[0], f"{fit_name} Fit - {y_columns[0]}"]
                    for legend in readback.get("legends", [])
                )
                native_range = fit_result.get("fit_range")
                range_ok = (
                    native_fit.get("full_range") is (fit_spec.fit_range is None)
                    and (native_range is None if fit_spec.fit_range is None else
                         tuple(native_range or ()) == fit_spec.fit_range)
                )
                if range_ok and fit_spec.fit_range is not None:
                    selected = selected_fit_points(pd.read_csv(staging_path), fit_spec)
                    regression = statistics.linear_regression(
                        selected[fit_spec.x_column], selected[fit_spec.y_column]
                    )
                    range_ok = (
                        fit_result.get("n_points") == len(selected)
                        and math.isclose(fit_result["parameters"]["slope"], regression.slope, rel_tol=1e-6)
                        and math.isclose(
                            fit_result["parameters"]["intercept"], regression.intercept, abs_tol=1e-6
                        )
                        and math.isclose(
                            fit_result["statistics"]["r_squared"],
                            statistics.correlation(
                                selected[fit_spec.x_column], selected[fit_spec.y_column]
                            ) ** 2,
                            abs_tol=1e-6,
                        )
                    )
                if not range_ok:
                    fit_ok = False
                    raise EngineError(
                        "fit_range_mismatch", "Saved Grapher Fit does not use the requested X interval",
                        engine="grapher",
                    )
                fit_ok = (
                    native_fit.get("present") is True
                    and native_fit.get("native_editable") is True
                    and native_fit.get("curve_present") is True
                    and range_ok
                    and native_fit.get("source_x_column_index") == 1
                    and native_fit.get("source_y_column_index") == staging_columns.index(y_columns[0]) + 1
                    and Path(native_fit.get("source_worksheet", "")).resolve() == staging_path
                    and fit_result.get("model") == fit_spec.model
                    and fit_result.get("degree") == fit_spec.degree
                    and native_fit.get("native_fit_type") == (0 if fit_spec.model == "linear" else 5)
                    and native_fit.get("native_degree") == fit_spec.degree
                    and fit_result.get("result_source") == "backend_native"
                    and fit_result.get("weight_mode") == "none"
                    and fit_result.get("n_points", 0) >= (3 if fit_spec.model == "polynomial" else 2)
                    and fit_legend
                )
            if "fits" in expected:
                native_fits = readback.get("fits") or {}
                fit_ok = set(native_fits) == set(y_columns)
                if fit_ok:
                    frame = pd.read_csv(staging_path)
                    for column, payload in zip(y_columns, expected["fits"], strict=True):
                        spec = FitSpec.from_dict(payload)
                        native = native_fits[column]
                        result = native.get("result") or {}
                        selected = selected_fit_points(frame, spec)
                        regression = statistics.linear_regression(
                            selected[spec.x_column], selected[spec.y_column]
                        )
                        fit_ok = fit_ok and all((
                            native.get("present") is True,
                            native.get("native_editable") is True,
                            native.get("full_range") is True,
                            native.get("source_x_column_index") == 1,
                            native.get("source_y_column_index") == staging_columns.index(column) + 1,
                            Path(native.get("source_worksheet", "")).resolve() == staging_path,
                            result.get("result_source") == "backend_native",
                            result.get("weight_mode") == "none",
                            result.get("n_points") == len(selected),
                            math.isclose(result["parameters"]["slope"], regression.slope, abs_tol=1e-6),
                            math.isclose(
                                result["parameters"]["intercept"], regression.intercept, abs_tol=1e-6
                            ),
                            math.isclose(
                                result["statistics"]["r_squared"],
                                statistics.correlation(selected[spec.x_column], selected[spec.y_column]) ** 2,
                                abs_tol=1e-6,
                            ),
                        ))
                if not fit_ok:
                    raise EngineError(
                        "fit_verify_failed", "Independent native Fits differ from XY series", engine="grapher"
                    )
        except Exception as exc:
            error = {"code": getattr(exc, "code", "grapher_verify_failed"), "message": str(exc)}
        reopened = bool(readback.get("document", {}).get("opened"))
        ok = (
            all(
                (
                    files_ok,
                    signatures_ok,
                    staging_ok,
                    reopened,
                    bindings_ok,
                    mode_ok,
                    legend_ok,
                    colors_ok,
                    title_ok,
                    axes_ok,
                    error_bindings_ok,
                    fit_ok,
                )
            )
            and error is None
        )
        report: dict[str, Any] = {
            "status": "ok" if ok else "failed",
            "engine": self.name,
            "editable_format": "grf",
            "output_directory": str(target),
            "artifacts": artifacts,
            "checks": {
                "files_nonempty": files_ok,
                "native_signatures": signatures_ok,
                "staging_integrity": staging_ok,
                "document_reopened": reopened,
                "plot_binding": bindings_ok,
                "line_symbol_mode": mode_ok,
                "chart_mode": mode_ok,
                "category_binding": mode_ok if is_bar else True,
                "legend_labels": legend_ok,
                "series_colors": colors_ok,
                "graph_title": title_ok,
                "axes": axes_ok,
                "error_bindings": error_bindings_ok,
                **({"native_fit": fit_ok} if "fit" in expected or "fits" in expected else {}),
            },
            "readback": readback,
        }
        if error:
            report["error"] = error
        try:
            _write_json(target / "grapher_verify_report.json", report)
        except OSError:
            pass
        return report


__all__ = ["GrapherEngine"]
