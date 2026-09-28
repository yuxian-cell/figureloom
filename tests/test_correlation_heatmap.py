"""Correlation semantics and mapping checks require no installed native application."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "src"))

from editaplot_engine.correlation_heatmap import CorrelationHeatmapSpec, grapher_classes, verify_readback
from editaplot_engine.models import EngineError


def spec(**updates):
    payload = {"labels": ["Control", "Treatment"], "correlation_matrix": [[1, -0.64], [-0.64, 1]]}
    payload.update(updates)
    return CorrelationHeatmapSpec.from_dict(payload)


def test_roundtrip_and_cell_coordinates():
    original = spec(p_value_matrix=[[1, 0.001], [0.001, 1]], significance={"enabled": True})
    assert CorrelationHeatmapSpec.from_dict(original.to_dict()) == original
    assert original.annotation(0, 0) == "1.00"
    assert original.annotation(0, 1) == "-0.64**"
    assert [(cell["x"], cell["y"]) for cell in original.cells()] == [(1, 2), (2, 2), (1, 1), (2, 1)]


@pytest.mark.parametrize(
    "p,stars", [(0.0009, "***"), (0.001, "**"), (0.009, "**"), (0.01, "*"), (0.049, "*"), (0.05, "")]
)
def test_strict_significance(p, stars):
    value = spec(p_value_matrix=[[0, p], [p, 0]], significance={"enabled": True})
    assert value.annotation(0, 1) == "-0.64" + stars
    assert value.annotation(0, 0) == "1.00"


@pytest.mark.parametrize(
    "updates,code",
    [
        ({"correlation_matrix": [[1], [1]]}, "invalid_correlation_matrix_shape"),
        ({"labels": ["Only"]}, "invalid_correlation_matrix"),
        ({"labels": ["A", "A"]}, "invalid_correlation_matrix"),
        ({"correlation_matrix": [[1, 0.1], [0.2, 1]]}, "invalid_correlation_matrix_symmetry"),
        ({"correlation_matrix": [[0.9, 0], [0, 1]]}, "invalid_correlation_diagonal"),
        ({"correlation_matrix": [[1, math.inf], [math.inf, 1]]}, "invalid_correlation_value"),
        ({"correlation_matrix": [[1, -1.0001], [-1.0001, 1]]}, "invalid_correlation_value"),
        ({"p_value_matrix": [[0, -0.1], [-0.1, 0]]}, "invalid_pvalue_range"),
        ({"p_value_matrix": [[0, math.nan], [math.nan, 0]]}, "invalid_pvalue_range"),
        ({"p_value_matrix": [[0]]}, "invalid_pvalue_matrix"),
        ({"significance": {"enabled": True}}, "invalid_pvalue_matrix"),
        ({"color_scale": {"min": 0, "max": 1}}, "color_mapping_mismatch"),
        ({"annotation": {"decimals": 2.5}}, "invalid_correlation_matrix"),
        ({"display": "lower_triangle"}, "invalid_correlation_matrix"),
        ({"labels": [f"L{i}" for i in range(21)]}, "correlation_matrix_too_large"),
    ],
)
def test_reject_invalid_scientific_input(updates, code):
    with pytest.raises(EngineError) as error:
        spec(**updates)
    assert error.value.code == code


def test_pvalues_do_not_enable_significance_implicitly():
    assert spec(p_value_matrix=[[0, 0.0001], [0.0001, 0]]).annotation(0, 1) == "-0.64"


def test_grapher_bins_cover_endpoints_and_zero_without_overlaps():
    bins = grapher_classes()
    assert len(bins) == 21
    assert bins[0]["min"] == -1 and bins[-1]["max"] == 1
    assert bins[10]["color"] == (255, 255, 255)
    assert bins[0]["color"] == (102, 194, 184)
    assert bins[-1]["color"] == (222, 120, 124)
    assert all(a["max"] == b["min"] for a, b in zip(bins, bins[1:], strict=False))
    assert bins[-1]["native_max"] == math.nextafter(1.0, math.inf)
    for value in [-1, -0.64, 0, 0.73, 1]:
        assert sum(item["min"] <= value < item["native_max"] for item in bins) == 1


def test_verify_rejects_changed_native_values_annotations_and_colors():
    import copy

    expected = spec()
    native = {
        "engine": "grapher",
        "source": "native_reopened_project",
        "plot_count": 1,
        "point_count": 4,
        "labels": list(expected.labels),
        "x_labels": list(expected.labels),
        "y_labels": list(expected.labels),
        "title": expected.title,
        "correlation_matrix": [list(row) for row in expected.correlation_matrix],
        "p_value_matrix": [[None, None], [None, None]],
        "cells": expected.cells(),
        "native_plot_type": 32,
        "class_column": 3,
        "x_column": 1,
        "y_column": 2,
        "legend": {"count": 21, "linked": [True] * 21},
        "mapping": {
            "mode": "discrete_classes",
            "classes": [
                {
                    "min": item["min"],
                    "max": item["native_max"],
                    "color": list(item["color"]),
                    "symbol_index": 10,
                }
                for item in grapher_classes()
            ],
        },
    }
    assert all(verify_readback(expected, native).values())
    changed = copy.deepcopy(native)
    changed["correlation_matrix"][0][1] = -0.2
    assert not verify_readback(expected, changed)["matrix_values"]
    changed = copy.deepcopy(native)
    changed["cells"][1]["annotation"] = "-0.64***"
    assert not verify_readback(expected, changed)["annotations"]
    changed = copy.deepcopy(native)
    changed["mapping"]["classes"][0]["color"] = [255, 0, 0]
    assert not verify_readback(expected, changed)["color_mapping"]
    changed = copy.deepcopy(native)
    changed["legend"]["linked"][0] = False
    assert not verify_readback(expected, changed)["linked_color_legend"]


def test_unsupported_engine_has_no_heatmap_fallback():
    from editaplot_engine.correlation_runtime import readback

    with pytest.raises(EngineError) as error:
        readback("wps", Path("result.grf"))
    assert error.value.code == "heatmap_unsupported_by_engine"
