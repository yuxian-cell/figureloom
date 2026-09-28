"""Scientific semantics for the correlation submode of the Heatmap route."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .models import EngineError

TOLERANCE = 1e-10
THRESHOLDS = ((0.001, "***"), (0.01, "**"), (0.05, "*"))
RECOMMENDED_MAX_SIZE = 10
MAX_SIZE = 20
HEATMAP_CAPABILITIES = {
    "origin": {
        "correlation_heatmap": True,
        "correlation_matrix": True,
        "native_matrix_plot": True,
        "pvalue_annotations": True,
        "native_color_scale": True,
        "mapping_mode": "native_colormap_levels",
        "color_levels": 256,
        "recommended_max_size": RECOMMENDED_MAX_SIZE,
        "max_size": MAX_SIZE,
    },
    "grapher": {
        "correlation_heatmap": True,
        "correlation_matrix": True,
        "generic_heatmap": False,
        "pvalue_annotations": True,
        "native_color_scale": True,
        "discrete_color_classes": True,
        "mapping_mode": "discrete_classes",
        "class_count": 21,
        "custom_continuous_mapping_verified": False,
        "recommended_max_size": RECOMMENDED_MAX_SIZE,
        "max_size": MAX_SIZE,
    },
}


def _matrix(value: Any, size: int, *, pvalues: bool = False) -> tuple[tuple[float, ...], ...]:
    code = "invalid_pvalue_matrix" if pvalues else "invalid_correlation_matrix_shape"
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise EngineError(code, "Matrix dimensions must match the ordered labels.")
    result = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != size:
            raise EngineError(code, "A square two-dimensional matrix is required.")
        if any(isinstance(item, (bool, str)) or not isinstance(item, (int, float)) for item in row):
            raise EngineError(code, "Matrix entries must be numeric.")
        converted = tuple(float(item) for item in row)
        lower = 0.0 if pvalues else -1.0
        if any(not math.isfinite(item) or item < lower or item > 1.0 for item in converted):
            raise EngineError(
                "invalid_pvalue_range" if pvalues else "invalid_correlation_value",
                "Matrix entries must be finite and within their scientific range.",
            )
        result.append(converted)
    return tuple(result)


@dataclass(frozen=True)
class CorrelationHeatmapSpec:
    labels: tuple[str, ...]
    correlation_matrix: tuple[tuple[float, ...], ...]
    p_value_matrix: tuple[tuple[float, ...], ...] | None = None
    show_value: bool = True
    decimals: int = 2
    significance_enabled: bool = False
    title: str = "Correlation"

    def __post_init__(self) -> None:
        if not isinstance(self.labels, (list, tuple)):
            raise EngineError("invalid_correlation_matrix", "Labels must be an ordered list.")
        labels = tuple(self.labels)
        if len(labels) < 2 or any(not isinstance(label, str) or not label.strip() for label in labels):
            raise EngineError("invalid_correlation_matrix", "At least two non-empty labels are required.")
        if len(set(labels)) != len(labels):
            raise EngineError("invalid_correlation_matrix", "Matrix labels must be unique.")
        if len(labels) > MAX_SIZE:
            raise EngineError(
                "correlation_matrix_too_large", "Native correlation heatmaps support at most 20 labels."
            )
        matrix = _matrix(self.correlation_matrix, len(labels))
        if any(abs(matrix[i][i] - 1.0) > TOLERANCE for i in range(len(labels))):
            raise EngineError("invalid_correlation_diagonal", "Correlation diagonal must equal one.")
        if any(abs(matrix[i][j] - matrix[j][i]) > TOLERANCE for i in range(len(labels)) for j in range(i)):
            raise EngineError("invalid_correlation_matrix_symmetry", "Correlation matrix is not symmetric.")
        pvalues = (
            None if self.p_value_matrix is None else _matrix(self.p_value_matrix, len(labels), pvalues=True)
        )
        if self.significance_enabled and pvalues is None:
            raise EngineError("invalid_pvalue_matrix", "Significance requires an explicit p-value matrix.")
        if type(self.decimals) is not int or not 0 <= self.decimals <= 6:
            raise EngineError(
                "invalid_correlation_matrix", "Annotation decimals must be an integer from zero to six."
            )
        if type(self.show_value) is not bool or type(self.significance_enabled) is not bool:
            raise EngineError("invalid_correlation_matrix", "Annotation flags must be booleans.")
        if not isinstance(self.title, str) or not self.title.strip():
            raise EngineError("invalid_correlation_matrix", "A non-empty title is required.")
        object.__setattr__(self, "labels", labels)
        object.__setattr__(self, "correlation_matrix", matrix)
        object.__setattr__(self, "p_value_matrix", pvalues)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CorrelationHeatmapSpec:
        if not isinstance(value, dict):
            raise EngineError("invalid_correlation_matrix", "Heatmap specification must be an object.")
        allowed = {
            "labels",
            "correlation_matrix",
            "p_value_matrix",
            "display",
            "color_scale",
            "annotation",
            "significance",
            "title",
        }
        if set(value) - allowed:
            raise EngineError("invalid_correlation_matrix", "Unknown correlation heatmap fields.")
        if value.get("display", "full_matrix") != "full_matrix":
            raise EngineError("invalid_correlation_matrix", "Only full matrix display is supported.")
        if value.get("color_scale", cls.color_scale()) != cls.color_scale():
            raise EngineError(
                "color_mapping_mismatch", "Correlation requires the fixed diverging [-1,1] scale."
            )
        annotation = value.get("annotation", {})
        significance = value.get("significance", {})
        if not isinstance(annotation, dict) or not isinstance(significance, dict):
            raise EngineError("invalid_correlation_matrix", "Annotation and significance must be objects.")
        if (
            set(annotation) - {"show_value", "decimals", "layout"}
            or annotation.get("layout", "single_text") != "single_text"
        ):
            raise EngineError("annotation_mismatch", "Only single-text cell annotations are supported.")
        if set(significance) - {"enabled", "thresholds", "comparison", "diagonal"}:
            raise EngineError("invalid_pvalue_matrix", "Unknown significance fields.")
        expected = cls.significance(False)
        for key in ("thresholds", "comparison", "diagonal"):
            if significance.get(key, expected[key]) != expected[key]:
                raise EngineError(
                    "invalid_pvalue_matrix", "This phase uses fixed strict significance thresholds."
                )
        return cls(
            labels=value.get("labels", ()),
            correlation_matrix=value.get("correlation_matrix", ()),
            p_value_matrix=value.get("p_value_matrix"),
            show_value=annotation.get("show_value", True),
            decimals=annotation.get("decimals", 2),
            significance_enabled=significance.get("enabled", False),
            title=value.get("title", "Correlation"),
        )

    @staticmethod
    def color_scale() -> dict[str, Any]:
        return {"min": -1.0, "max": 1.0, "type": "diverging", "palette_id": "correlation_diverging"}

    @staticmethod
    def significance(enabled: bool) -> dict[str, Any]:
        return {
            "enabled": enabled,
            "thresholds": [{"p": p, "text": text} for p, text in THRESHOLDS],
            "comparison": "strict_less_than",
            "diagonal": "none",
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "labels": list(self.labels),
            "correlation_matrix": [list(row) for row in self.correlation_matrix],
            "p_value_matrix": None
            if self.p_value_matrix is None
            else [list(row) for row in self.p_value_matrix],
            "display": "full_matrix",
            "color_scale": self.color_scale(),
            "annotation": {"show_value": self.show_value, "decimals": self.decimals, "layout": "single_text"},
            "significance": self.significance(self.significance_enabled),
            "title": self.title,
        }

    def annotation(self, row: int, column: int) -> str:
        text = format(self.correlation_matrix[row][column], f".{self.decimals}f") if self.show_value else ""
        if self.significance_enabled and row != column and self.p_value_matrix is not None:
            text += next(
                (stars for limit, stars in THRESHOLDS if self.p_value_matrix[row][column] < limit), ""
            )
        return text

    def cells(self) -> list[dict[str, Any]]:
        size = len(self.labels)
        return [
            {
                "row": i,
                "column": j,
                "x": j + 1,
                "y": size - i,
                "row_label": self.labels[i],
                "column_label": self.labels[j],
                "r": value,
                "p": None if self.p_value_matrix is None else self.p_value_matrix[i][j],
                "annotation": self.annotation(i, j),
            }
            for i, row in enumerate(self.correlation_matrix)
            for j, value in enumerate(row)
        ]


def diverging_rgb(value: float) -> tuple[int, int, int]:
    endpoint = (102, 194, 184) if value < 0 else (222, 120, 124)
    return tuple(round(255 + (color - 255) * abs(value)) for color in endpoint)


def validate_source(spec: CorrelationHeatmapSpec, path: Any) -> None:
    """Bind the frozen matrix to the existing table reader, never infer correlations."""
    from origin_sciplot.data_loader import load_table

    frame = load_table(path).frame
    if frame.shape != (len(spec.labels), len(spec.labels) + 1):
        raise EngineError("invalid_correlation_matrix_shape", "Source must be a labeled square matrix table.")
    if (
        tuple(str(column) for column in frame.columns[1:]) != spec.labels
        or tuple(str(value) for value in frame.iloc[:, 0]) != spec.labels
    ):
        raise EngineError("invalid_correlation_matrix", "Source row and column labels must match in order.")
    try:
        values = frame.iloc[:, 1:].astype(float).values.tolist()
    except (ValueError, TypeError) as exc:
        raise EngineError("invalid_correlation_value", "Source matrix must be numeric.") from exc
    native = CorrelationHeatmapSpec(labels=spec.labels, correlation_matrix=values)
    if native.correlation_matrix != spec.correlation_matrix:
        raise EngineError("invalid_correlation_matrix", "Frozen correlations differ from source values.")


def grapher_classes() -> list[dict[str, Any]]:
    """21 centered bins; +1 is included by an explicit native exclusive-bound adjustment."""
    edges = [-1.0] + [round(-0.95 + index * 0.1, 12) for index in range(20)] + [1.0]
    return [
        {
            "min": edges[i],
            "max": edges[i + 1],
            "native_max": edges[i + 1] if i < 20 else math.nextafter(1.0, math.inf),
            "color": diverging_rgb(round(-1.0 + i * 0.1, 12)),
        }
        for i in range(21)
    ]


def verify_readback(spec: CorrelationHeatmapSpec, native: dict[str, Any]) -> dict[str, bool]:
    """The expected spec is a comparator; every actual value must come from native readback."""
    size = len(spec.labels)
    checks = {
        "native_reopened": native.get("source") == "native_reopened_project",
        "native_plot": native.get("plot_count") == 1,
        "cell_count": native.get("point_count") == size * size,
        "labels": all(native.get(key) == list(spec.labels) for key in ("labels", "x_labels", "y_labels")),
        "title": native.get("title") == spec.title,
    }
    matrix = native.get("correlation_matrix", [])
    checks["matrix_values"] = len(matrix) == size and all(
        len(row) == size
        and all(
            isinstance(actual, (int, float)) and math.isfinite(actual) and abs(actual - expected) <= TOLERANCE
            for actual, expected in zip(row, spec.correlation_matrix[index], strict=True)
        )
        for index, row in enumerate(matrix)
    )
    expected_pvalues = (
        [list(row) for row in spec.p_value_matrix]
        if spec.p_value_matrix is not None
        else [[None] * size for _ in range(size)]
    )
    checks["pvalues"] = native.get("p_value_matrix") == expected_pvalues
    cells = native.get("cells", [])
    expected_cells = spec.cells()
    checks["annotations"] = len(cells) == size * size and all(
        actual.get("row") == expected["row"]
        and actual.get("column") == expected["column"]
        and actual.get("row_label") == expected["row_label"]
        and actual.get("column_label") == expected["column_label"]
        and actual.get("annotation") == expected["annotation"]
        for actual, expected in zip(cells, expected_cells, strict=True)
    )
    mapping = native.get("mapping", {})
    if native.get("engine") == "grapher":
        definitions = grapher_classes()
        classes = mapping.get("classes", [])
        checks["color_mapping"] = (
            mapping.get("mode") == "discrete_classes"
            and len(classes) == 21
            and all(
                actual.get("min") == expected["min"]
                and actual.get("max") == expected["native_max"]
                and actual.get("color") == list(expected["color"])
                and actual.get("symbol_index") == 10
                for actual, expected in zip(classes, definitions, strict=True)
            )
        )
        checks["native_binding"] = (
            native.get("native_plot_type") == 32
            and native.get("class_column") == 3
            and native.get("x_column") == 1
            and native.get("y_column") == 2
        )
        legend = native.get("legend", {})
        checks["linked_color_legend"] = legend.get("count") == 21 and legend.get("linked") == [True] * 21
    else:
        levels = [-1 + 2 * index / 256 for index in range(257)]
        colors = [list(diverging_rgb(-1 + 2 * (index - 0.5) / 256)) for index in range(1, 257)]
        checks["color_mapping"] = (
            mapping.get("mode") == "native_colormap_levels"
            and mapping.get("levels") == levels
            and mapping.get("colors") == colors
            and mapping.get("min") == -1
            and mapping.get("max") == 1
        )
        checks["native_binding"] = bool(native.get("native_matrix"))
        legend = native.get("legend", {})
        checks["linked_color_legend"] = (
            legend.get("visible") is True
            and legend.get("linked") is True
            and legend.get("min") == -1
            and legend.get("max") == 1
        )
    return checks
