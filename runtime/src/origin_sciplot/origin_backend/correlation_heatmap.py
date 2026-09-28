"""Matrix-backed Origin correlation Heatmap, native annotations and color scale."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from editaplot_engine.correlation_heatmap import CorrelationHeatmapSpec, diverging_rgb
from editaplot_engine.models import EngineError

from .base_style_contract import FixedOriginStyle
from .categorical_renderer import _set_page_size
from .export_utils import export_graph

GRAPH_NAME = "CorrelationHeatmap"


def _label(
    layer: Any, name: str, text: str, x: float, y: float, *, rotation: float = 0, size: float = 9
) -> None:
    layer.obj.LT_execute(f"label -j 1 -n {name} pending;")
    label = layer.label(name)
    label.text = text
    label.set_int("attach", 2)
    label.set_float("rotate", rotation)
    label.set_float("fsize", size)
    label.set_int("justify", 1)
    label.set_int("showframe", 0)
    # Update the native text bounds before positioning its center.
    layer.obj.LT_execute(f"{name}.font=font(Arial);{name}.bold=0;doc -uw;")
    label.set_float("x", x)
    label.set_float("y", y)


def create(op: Any, spec: CorrelationHeatmapSpec, target: Path) -> Path:
    size = len(spec.labels)
    matrix = op.new_sheet("m", "Correlation Matrix")
    matrix.from_np(np.asarray(spec.correlation_matrix))
    matrix.xymap = (1, size, 1, size)
    provenance = op.new_sheet("w", "Correlation Cell Semantics")
    provenance.from_df(pd.DataFrame(spec.cells()))
    graph = op.new_graph(spec.title, template="heatmap")
    graph.name = GRAPH_NAME
    layer = graph[0]
    plot = layer.add_plot(matrix, colz=0)
    layer.rescale("z")
    _set_page_size(graph, FixedOriginStyle(page_width_cm=21.59, page_height_cm=19.05))
    layer.set_int("unit", 1)
    for key, value in {"left": 18, "top": 12, "width": 61, "height": 69}.items():
        layer.set_float(key, value)
    plot.zlevels = {"minors": 0, "levels": [-1 + 2 * index / 256 for index in range(257)]}
    layer.set_int("cmap.linkpal", 0)
    for index in range(1, 257):
        rgb = diverging_rgb(-1 + 2 * (index - 0.5) / 256)
        layer.set_int(f"cmap.color{index}", op.ocolor(rgb))
    layer.obj.LT_execute("layer.cmap.updateScale();")
    layer.axis("x").set_limits(0.5, size + 0.5, 1)
    layer.axis("y").set_limits(size + 0.5, 0.5, 1)
    for axis in ("x", "y"):
        layer.set_int(f"{axis}.showLabels", 0)
        layer.set_int(f"{axis}.label.show", 0)
        layer.set_float(f"{axis}.ticklength", 0)
        layer.set_float(f"{axis}.mticklength", 0)
        layer.axis(axis).title = ""
        layer.set_float(f"{axis}.firstTick", 0.5)
        layer.set_int(f"{axis}.grid.show", 1)
        layer.set_int(f"{axis}.grid.majorColor", op.ocolor((255, 255, 255)))
        layer.set_float(f"{axis}.grid.majorWidth", 0.5)
    layer.obj.LT_execute("layer -b g 1;")
    for name in ("legend", "xb", "yl"):
        if layer.label(name) is not None:
            layer.remove_label(name)
    for index, text in enumerate(spec.labels):
        _label(layer, f"CHX{index}", text, index + 1, size + 0.85, rotation=45)
        _label(layer, f"CHY{index}", text, 0.05, index + 1)
    for cell in spec.cells():
        if cell["annotation"]:
            _label(
                layer,
                f"CHC{cell['row']}X{cell['column']}",
                cell["annotation"],
                cell["column"] + 1,
                cell["row"] + 1,
                size=max(6, min(10, 80 / size)),
            )
    _label(layer, "CHTitle", spec.title, (size + 1) / 2, 0.2, size=14)
    # The native graph retains a relationship to its annotation/p-value backing worksheet.
    _label(layer, "CHBacking", provenance.lt_range(), 1, 1)
    layer.label("CHBacking").set_int("show", 0)
    layer.obj.LT_execute(
        "spectrum1.show=1;spectrum1.title=0;spectrum1.attach=0;"
        "spectrum1.labels.autodisp=0;spectrum1.labels.font=font(Arial);"
        "spectrum1.labels.fsize=10;spectrum1.labels.underline=0;"
        "spectrum1.left=page.width*0.83;spectrum1.top=page.height*0.12;"
        "spectrum1.width=page.width*0.07;spectrum1.height=page.height*0.69;"
        "spectrum1.levels.major=3;spectrum1.levels.from=-1;spectrum1.levels.to=1;"
        "spectrum1.levels.inc=0;spectrum1.levels.majorticks=3;spectrum1.levels.minorticks=0;"
    )
    op.save(str(target / "result.opju"))
    export_graph(op, graph, target / "result.png", target / "result.pdf", target / "result.tif")
    op.new(asksave=False)
    return target / "result.opju"


def read_opened(op: Any) -> dict[str, Any]:
    graph = op.find_graph(GRAPH_NAME)
    if graph is None:
        raise EngineError("heatmap_readback_failed", "Native correlation graph is missing.")
    graph.activate()
    layer = graph[0]
    plots = layer.plot_list()
    if len(plots) != 1:
        raise EngineError("heatmap_readback_failed", "Expected one native matrix Heatmap.")
    plot = plots[0]
    dataset = plot.obj.GetDatasetName()
    matrix = op.find_sheet("m", dataset)
    if matrix is None:
        raise EngineError("heatmap_readback_failed", "Heatmap native matrix relationship is missing.")
    values = matrix.to_np2d().tolist()
    size = len(values)
    x_labels = [layer.label(f"CHX{index}").text for index in range(size)]
    y_labels = [layer.label(f"CHY{index}").text for index in range(size)]
    provenance = op.find_sheet("w", layer.label("CHBacking").text)
    records = provenance.to_df().to_dict("records")
    cells = []
    pvalues = [[None] * size for _ in range(size)]
    for record in records:
        row, column = int(record["row"]), int(record["column"])
        native_text = layer.label(f"CHC{row}X{column}")
        pvalue = record["p"]
        pvalues[row][column] = None if pd.isna(pvalue) or pvalue == "" else float(pvalue)
        cells.append(
            {
                "row": row,
                "column": column,
                "r": values[row][column],
                "row_label": y_labels[row],
                "column_label": x_labels[column],
                "annotation": native_text.text if native_text else "",
            }
        )
    colors = []
    for index in range(1, int(layer.get_int("cmap.numColors")) + 1):
        color = layer.get_int(f"cmap.color{index}")
        colors.append([color & 255, (color >> 8) & 255, (color >> 16) & 255])
    return {
        "engine": "origin",
        "family": "correlation_heatmap",
        "source": "native_reopened_project",
        "plot_count": len(plots),
        "native_matrix": dataset,
        "point_count": size * size,
        "labels": y_labels,
        "x_labels": x_labels,
        "y_labels": y_labels,
        "correlation_matrix": values,
        "p_value_matrix": pvalues,
        "cells": cells,
        "title": layer.label("CHTitle").text,
        "mapping": {
            "mode": "native_colormap_levels",
            "levels": plot.zlevels["levels"],
            "colors": colors,
            "min": layer.get_float("cmap.zmin"),
            "max": layer.get_float("cmap.zmax"),
        },
        "legend": {
            "visible": bool(op.lt_float("spectrum1.show")),
            # spectrum1 is Origin's native scale for this single matrix plot's cmap.
            "linked": bool(layer.label("spectrum1")),
            "min": op.lt_float("spectrum1.levels.from"),
            "max": op.lt_float("spectrum1.levels.to"),
            "relationship_source": "single_matrix_plot_native_spectrum",
        },
    }


def read(op: Any, path: Path) -> dict[str, Any]:
    if not op.open(str(path), asksave=False):
        raise EngineError("heatmap_readback_failed", "Saved OPJU could not reopen.")
    try:
        return read_opened(op)
    finally:
        op.new(asksave=False)
