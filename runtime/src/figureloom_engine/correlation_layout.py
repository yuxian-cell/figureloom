"""Physical, deterministic layout for the bounded correlation Heatmap submode."""

from __future__ import annotations

import math
import unicodedata
from typing import Any

from .correlation_heatmap import CorrelationHeatmapSpec


def text_width_inches(text: str, font_pt: float) -> float:
    """Conservative Arial-like advance estimate, independent of GUI/font installation."""
    units = 0.0
    for char in text:
        if unicodedata.combining(char):
            continue
        if unicodedata.east_asian_width(char) in ("W", "F"):
            units += 1.0
        elif char in "ilI.,:;!'| ":
            units += 0.3
        elif char in "MWmw@%":
            units += 0.9
        elif char.isupper():
            units += 0.7
        elif char in "_*+-" or char.isdigit():
            units += 0.6
        else:
            units += 0.56
    return units * font_pt / 72


def plan_layout(spec: CorrelationHeatmapSpec, engine: str) -> dict[str, Any]:
    if engine not in ("origin", "grapher"):
        raise ValueError("Correlation layout requires a supported native engine.")
    size = len(spec.labels)
    label_font = 10.0
    annotation_font = 11.0 if engine == "origin" else 10.0
    label_width = max(text_width_inches(label, label_font) for label in spec.labels)
    annotations = [cell["annotation"] for cell in spec.cells() if cell["annotation"]]
    annotation_width = max((text_width_inches(text, annotation_font) for text in annotations), default=0.0)
    # ponytail: approximate glyph advances; enlarge physical cells, never shrink text.
    cell = math.ceil(max(0.55, annotation_width + 0.24) * 100) / 100
    label_height = label_font * 1.3 / 72
    rotation = 90
    for candidate in (45, 60, 90):
        angle = math.radians(candidate)
        projection = label_width * math.cos(angle) + label_height * math.sin(angle)
        if projection <= cell - 0.12:
            rotation = candidate
            break
    angle = math.radians(rotation)
    rotated_height = label_width * math.sin(angle) + label_height * math.cos(angle)
    left = label_width + 0.4
    bottom = rotated_height + 0.45
    span = size * cell
    top = 0.7 if spec.title else 0.35
    legend_width = 1.25 if engine == "origin" else 2.25
    # Reserve full native 21-entry legend height even for a 2x2 matrix.
    legend_height = span if engine == "origin" else max(span, 4.65)
    height = bottom + max(span, legend_height) + top
    if legend_height > span:
        bottom += (legend_height - span) / 2
    width = left + span + 0.35 + legend_width
    width = max(width, text_width_inches(spec.title, 14) + 0.8)
    return {
        "schema_version": "1.0",
        "profile": "compact" if size <= 8 and label_width <= 1.0 else "expanded",
        "matrix_size": size,
        "max_label_length": max(map(len, spec.labels)),
        "max_label_width_in": round(label_width, 6),
        "max_annotation_width_in": round(annotation_width, 6),
        "annotation_count": len(annotations),
        "page_width_in": round(width, 6),
        "page_height_in": round(height, 6),
        "plot_left_in": round(left, 6),
        "plot_bottom_in": round(bottom, 6),
        "plot_span_in": round(span, 6),
        "cell_size_in": cell,
        "label_font_pt": label_font,
        "annotation_font_pt": annotation_font,
        "x_rotation_deg": rotation,
        "x_label_height_in": round(rotated_height, 6),
        "legend_width_in": legend_width,
        "legend_left_in": round(left + span + 0.35, 6),
        "title_font_pt": 14.0,
        "warnings": ["Dense matrix (>10 labels): inspect native text at intended physical size."]
        if size > 10
        else [],
    }


def layouts(spec: CorrelationHeatmapSpec) -> dict[str, dict[str, Any]]:
    return {engine: plan_layout(spec, engine) for engine in ("origin", "grapher")}


def verify_layout(expected: dict[str, Any], native: dict[str, Any]) -> bool:
    """Compare only attributes actually recovered from the reopened native project."""
    actual = native.get("layout", {})
    keys = ("page_width_in", "page_height_in", "plot_left_in", "plot_bottom_in", "plot_span_in")
    if not all(
        isinstance(actual.get(key), (int, float))
        and math.isfinite(actual[key])
        and abs(actual[key] - expected[key]) <= 0.015
        for key in keys
    ):
        return False
    if abs(actual.get("plot_height_in", 0) - expected["plot_span_in"]) > 0.015:
        return False
    size = expected["matrix_size"]
    for key, target, count in (
        ("x_label_font_pt", expected["label_font_pt"], size),
        ("y_label_font_pt", expected["label_font_pt"], size),
    ):
        values = actual.get(key, [])
        if len(values) != count or any(
            not math.isfinite(value) or abs(value - target) > 0.05 for value in values
        ):
            return False
    if native.get("engine") == "origin":
        angles = actual.get("x_label_rotation_deg", [])
        if len(angles) != size or any(
            not math.isfinite(v) or abs(v - expected["x_rotation_deg"]) > 0.05 for v in angles
        ):
            return False
    else:
        bounds = actual.get("x_label_bounds_in", [])
        if len(bounds) != size:
            return False
        for box in bounds:
            if not all(math.isfinite(box[key]) for key in ("left", "top", "width", "height")):
                return False
            if (
                box["left"] < 0
                or box["left"] + box["width"] > expected["page_width_in"]
                or box["top"] > expected["plot_bottom_in"] - 0.04
                or box["top"] - box["height"] < 0
            ):
                return False
        ordered = sorted(bounds, key=lambda box: box["left"])
        if any(
            a["left"] + a["width"] > b["left"] + 0.015 for a, b in zip(ordered, ordered[1:], strict=False)
        ):
            return False
    fonts = actual.get("annotation_font_pt", [])
    return len(fonts) == expected["annotation_count"] and all(
        math.isfinite(value) and abs(value - expected["annotation_font_pt"]) <= 0.05 for value in fonts
    )
