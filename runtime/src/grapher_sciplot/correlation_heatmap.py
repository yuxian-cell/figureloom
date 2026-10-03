"""Native class-scatter correlation cells with a linked class legend."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from figureloom_engine.correlation_heatmap import CorrelationHeatmapSpec, grapher_classes
from figureloom_engine.correlation_layout import plan_layout
from figureloom_engine.models import EngineError

from .smoke import call, get, open_document, put, require_file

GRAPH_NAME = "FigureLoom Correlation Heatmap"


def _rgb(value: tuple[int, int, int]) -> int:
    return value[0] | value[1] << 8 | value[2] << 16


def _text(
    shapes: Any,
    name: str,
    x: float,
    y: float,
    value: str,
    *,
    size: float = 10,
    align: int = 2,
    rotation: float = 0,
) -> None:
    text = call(shapes, "AddText", x, y, value)
    put(text, "Name", name)
    font = get(text, "Font")
    for key, setting in {"face": "Arial", "size": size, "HAlign": align, "VAlign": 4}.items():
        put(font, key, setting)
    put(text, "Rotation", rotation)


def create(app: Any, spec: CorrelationHeatmapSpec, target: Path, layout: dict | None = None) -> Path:
    size = len(spec.labels)
    layout = layout or plan_layout(spec, "grapher")
    left, bottom = layout["plot_left_in"], layout["plot_bottom_in"]
    staging = target / "correlation_cells.csv"
    with staging.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["X", "Y", "Correlation", "RowLabel", "ColumnLabel", "PValue"])
        writer.writerows(
            [cell["x"], cell["y"], cell["r"], cell["row_label"], cell["column_label"], cell["p"]]
            for cell in spec.cells()
        )
    staging_already_open = _find_worksheet(app, staging) is not None
    document = call(get(app, "Documents"), "Add", 0)
    try:
        shapes = get(document, "Shapes")
        page = get(document, "PageSetup")
        cell_width = layout["cell_size_in"]
        span = layout["plot_span_in"]
        put(page, "pageSize", -1)
        put(page, "width", layout["page_width_in"])
        put(page, "height", layout["page_height_in"])
        graph = call(shapes, "AddClassPlotGraph", str(staging), 1, 2, 3)
        put(graph, "Name", GRAPH_NAME)
        put(graph, "LinkTitleToObjectName", False)
        put(get(graph, "title"), "text", "")
        plot = call(get(graph, "Plots"), "Item", 1)
        put(plot, "Name", "Correlation matrix cells")
        put(plot, "Method", 2)
        call(plot, "DeleteAllClasses")
        put(plot, "UseIncrementalSymSize", False)
        put(plot, "DefaultSymSize", cell_width)
        put(get(plot, "line"), "style", "Invisible")
        for definition in grapher_classes():
            call(plot, "AddClass", definition["min"], definition["native_max"], "")
            symbol = call(plot, "ClassSymbol", int(get(plot, "NumberOfClasses")))
            put(symbol, "Index", 10)
            put(symbol, "size", cell_width)
            put(get(symbol, "Fill"), "foreColor", _rgb(definition["color"]))
            put(get(symbol, "line"), "foreColor", 16777215)
            put(get(symbol, "line"), "width", 0.006)
        put(plot, "DisplayLegend", True)
        for index in (1, 2):
            axis = call(get(graph, "Axes"), "Item", index)
            for name, setting in {
                "AutoMin": False,
                "AutoMax": False,
                "Min": 0.5,
                "Max": size + 0.5,
                "length": span,
                "xPos": left,
                "yPos": bottom,
            }.items():
                put(axis, name, setting)
            put(get(axis, "title"), "text", "")
            put(get(axis, "line"), "style", "Invisible")
            put(get(axis, "TickLabels"), "MajorOn", False)
            put(get(axis, "TickLabels"), "MinorOn", False)
            put(get(axis, "Tickmarks"), "MajorSide", 0)
            put(get(axis, "Tickmarks"), "MinorSide", 0)
            put(get(axis, "Grid"), "AtMajorTicks", False)
            put(get(axis, "Grid"), "AtMinorTicks", False)
        for index, label in enumerate(spec.labels):
            _text(
                shapes,
                f"CH_X_{index}",
                left + (index + 0.5) * cell_width,
                bottom - 0.15 - layout["x_label_height_in"] / 2,
                label,
                size=layout["label_font_pt"],
                align=2,
                rotation=layout["x_rotation_deg"],
            )
            _text(
                shapes,
                f"CH_Y_{index}",
                left - 0.15,
                bottom + (size - index - 0.5) * cell_width,
                label,
                size=layout["label_font_pt"],
                align=3,
            )
        for cell in spec.cells():
            if cell["annotation"]:
                _text(
                    shapes,
                    f"CH_CELL_{cell['row']}_{cell['column']}",
                    left + (cell["column"] + 0.5) * cell_width,
                    bottom + (size - cell["row"] - 0.5) * cell_width,
                    cell["annotation"],
                    size=layout["annotation_font_pt"],
                )
        _text(
            shapes,
            "CH_TITLE",
            left + span / 2,
            bottom + span + 0.35,
            spec.title,
            size=layout["title_font_pt"],
        )
        legend = call(get(graph, "Legends"), "Item", 1)
        put(legend, "TitleLinked", False)
        put(legend, "TitleText", "r (21 bins; +1 included)")
        put(get(legend, "TitleFont"), "size", 10)
        put(legend, "ShowEmptyClasses", True)
        put(legend, "DrawDescending", True)
        put(get(legend, "line"), "style", "Invisible")
        put(legend, "RowOffset", 0.045)
        for index in range(1, 22):
            call(legend, "EntrySymbolMode", index, 2)
            call(legend, "EntrySymbolSize", index, 0.11)
            put(call(legend, "EntryFont", index), "size", 9)
        put(legend, "left", layout["legend_left_in"])
        put(legend, "top", bottom + span)
        # Native interval entries remain linked; a decorative gradient would hide the bins.
        put(get(legend, "Font"), "size", 9)
        path = target / "result.grf"
        call(document, "SaveAs", str(path))
        require_file(path, "heatmap_render_failed")
        for suffix, options in {
            "png": "Defaults=1,ForgetOptions=1,HDPI=250,VDPI=250",
            "pdf": "Defaults=1,ForgetOptions=1,EmbedFonts=1,FitPage=1",
        }.items():
            exported = target / f"result.{suffix}"
            call(
                document, "Export2", str(exported), False, options, True, "png" if suffix == "png" else "pdfv"
            )
            require_file(exported, "heatmap_render_failed")
        return path
    finally:
        call(document, "Close", False)
        if not staging_already_open:
            worksheet = _find_worksheet(app, staging)
            if worksheet is not None:
                call(worksheet, "Close", False)


def _find_worksheet(app: Any, path: Path) -> Any | None:
    documents = get(app, "Documents")
    for index in range(1, int(get(documents, "Count")) + 1):
        document = call(documents, "Item", index)
        if Path(str(get(document, "FullName"))).resolve() == path.resolve():
            return document
    return None


def _worksheet_values(plot: Any, preexisting_paths: set[Path]) -> Any:
    """Close the backing worksheet only when this readback opened it."""
    path = Path(str(get(plot, "worksheet"))).resolve()
    already_open = path in preexisting_paths
    worksheet = call(plot, "DisplayWorksheet")
    try:
        return get(get(worksheet, "UsedRange"), "Value")
    finally:
        if not already_open:
            call(worksheet, "Close", False)


def read_document(document: Any, preexisting_paths: set[Path]) -> dict[str, Any]:
    shapes = get(document, "Shapes")
    graph = call(shapes, "Item", GRAPH_NAME)
    plots = get(graph, "Plots")
    plot = call(plots, "Item", 1)
    values = _worksheet_values(plot, preexisting_paths)
    header, *records = values
    if tuple(header) != ("X", "Y", "Correlation", "RowLabel", "ColumnLabel", "PValue"):
        raise EngineError("heatmap_readback_failed", "Native worksheet has unexpected columns.")
    size = math.isqrt(len(records))
    if size * size != len(records):
        raise EngineError("heatmap_readback_failed", "Native cell count is not square.")
    labels = [str(records[i * size][3]) for i in range(size)]
    matrix = [[None] * size for _ in range(size)]
    pvalues = [[None] * size for _ in range(size)]
    cells = []
    for record in records:
        x, y, value, row_label, column_label, pvalue = record
        if float(x) != int(x) or float(y) != int(y):
            raise EngineError(
                "heatmap_readback_failed", "Native cell coordinates must be integer grid positions."
            )
        row, column = size - int(y), int(x) - 1
        if not 0 <= row < size or not 0 <= column < size or matrix[row][column] is not None:
            raise EngineError("heatmap_readback_failed", "Native grid coordinates are invalid.")
        matrix[row][column] = float(value)
        pvalues[row][column] = None if pvalue in (None, "") else float(pvalue)
        try:
            annotation = str(get(call(shapes, "Item", f"CH_CELL_{row}_{column}"), "text"))
        except Exception:
            annotation = ""
        cells.append(
            {
                "row": row,
                "column": column,
                "x": x,
                "y": y,
                "r": float(value),
                "row_label": str(row_label),
                "column_label": str(column_label),
                "annotation": annotation,
            }
        )
    classes = []
    for index in range(1, int(get(plot, "NumberOfClasses")) + 1):
        symbol = call(plot, "ClassSymbol", index)
        color = int(get(get(symbol, "Fill"), "foreColor"))
        classes.append(
            {
                "min": call(plot, "GetClassMin", index),
                "max": call(plot, "GetClassMax", index),
                "color": [color & 255, (color >> 8) & 255, (color >> 16) & 255],
                "symbol_index": get(symbol, "Index"),
            }
        )
    legend = call(get(graph, "Legends"), "Item", 1)
    return {
        "engine": "grapher",
        "family": "correlation_heatmap",
        "source": "native_reopened_project",
        "native_plot_type": get(plot, "PlotType"),
        "plot_count": get(plots, "Count"),
        "point_count": get(plot, "DataPtsCount"),
        "class_column": get(plot, "classCol"),
        "x_column": get(plot, "xCol"),
        "y_column": get(plot, "yCol"),
        "labels": labels,
        "x_labels": [str(get(call(shapes, "Item", f"CH_X_{i}"), "text")) for i in range(size)],
        "y_labels": [str(get(call(shapes, "Item", f"CH_Y_{i}"), "text")) for i in range(size)],
        "correlation_matrix": matrix,
        "p_value_matrix": pvalues,
        "cells": cells,
        "title": str(get(call(shapes, "Item", "CH_TITLE"), "text")),
        "layout": {
            "page_width_in": get(get(document, "PageSetup"), "width"),
            "page_height_in": get(get(document, "PageSetup"), "height"),
            "plot_left_in": get(call(get(graph, "Axes"), "Item", 1), "xPos"),
            "plot_bottom_in": get(call(get(graph, "Axes"), "Item", 1), "yPos"),
            "plot_span_in": get(call(get(graph, "Axes"), "Item", 1), "length"),
            "plot_height_in": get(call(get(graph, "Axes"), "Item", 2), "length"),
            # Text shape Rotation returns 0 even for rotated glyphs in Grapher 27.
            # Preserve the actual COM value, not the planned angle as a fake readback.
            "x_label_shape_rotation_deg": [
                get(call(shapes, "Item", f"CH_X_{i}"), "Rotation") for i in range(size)
            ],
            "x_label_bounds_in": [
                {
                    key: get(call(shapes, "Item", f"CH_X_{i}"), key)
                    for key in ("left", "top", "width", "height")
                }
                for i in range(size)
            ],
            "x_label_font_pt": [
                get(get(call(shapes, "Item", f"CH_X_{i}"), "Font"), "size") for i in range(size)
            ],
            "y_label_font_pt": [
                get(get(call(shapes, "Item", f"CH_Y_{i}"), "Font"), "size") for i in range(size)
            ],
            "annotation_font_pt": [
                get(get(call(shapes, "Item", f"CH_CELL_{c['row']}_{c['column']}"), "Font"), "size")
                for c in cells
                if c["annotation"]
            ],
        },
        "mapping": {"mode": "discrete_classes", "classes": classes},
        "legend": {
            "count": get(legend, "EntryCount"),
            "linked": [
                bool(call(legend, "EntryDefault", i)) for i in range(1, int(get(legend, "EntryCount")) + 1)
            ],
        },
    }


def read(app: Any, path: Path) -> dict[str, Any]:
    # Opening a GRF can also open its backing worksheet. Snapshot before Open,
    # so that this native side effect is not mistaken for a user's document.
    documents = get(app, "Documents")
    preexisting_paths = {
        Path(str(get(call(documents, "Item", index), "FullName"))).resolve()
        for index in range(1, int(get(documents, "Count")) + 1)
    }
    document = open_document(app, path)
    try:
        return read_document(document, preexisting_paths)
    finally:
        call(document, "Close", False)
