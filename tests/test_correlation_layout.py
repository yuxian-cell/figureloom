"""Layout choices do not alter the scientific correlation contract."""

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime/src"))
from editaplot_engine.correlation_heatmap import CorrelationHeatmapSpec  # noqa: E402
from editaplot_engine.correlation_layout import plan_layout, text_width_inches, verify_layout  # noqa: E402

FIXTURES = ROOT / "tests/fixtures/correlation_heatmap"


def concrete(pvalues=True):
    def load(name):
        with (FIXTURES / name).open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        return rows[0][1:], [[float(v) for v in row[1:]] for row in rows[1:]]

    labels, matrix = load("concrete_correlation.csv")
    _, probabilities = load("concrete_pvalues.csv")
    return CorrelationHeatmapSpec(
        labels,
        matrix,
        probabilities if pvalues else None,
        significance_enabled=pvalues,
        title="Concrete correlation",
    )


@pytest.mark.parametrize("engine", ["origin", "grapher"])
@pytest.mark.parametrize("size", [8, 9, 10, 11, 20])
@pytest.mark.parametrize("annotations", [False, True])
def test_layout_boundaries(engine, size, annotations):
    labels = [f"Demo_{i}" for i in range(size)]
    spec = CorrelationHeatmapSpec(
        labels, [[float(i == j) for j in range(size)] for i in range(size)], show_value=annotations
    )
    before = spec.to_dict()
    result = plan_layout(spec, engine)
    assert result == plan_layout(spec, engine)
    assert bool(result["warnings"]) == (size > 10)
    assert result["annotation_font_pt"] >= 10
    assert result["plot_span_in"] / size == pytest.approx(result["cell_size_in"])
    assert result["page_width_in"] > result["plot_left_in"] + result["plot_span_in"]
    assert result["page_height_in"] > result["plot_bottom_in"] + result["plot_span_in"]
    assert result["annotation_count"] == (size * size if annotations else 0)
    assert spec.to_dict() == before
    if size == 8:
        assert result["profile"] == "compact"


@pytest.mark.parametrize("engine", ["origin", "grapher"])
def test_concrete_long_labels_and_stars(engine):
    spec = concrete()
    result = plan_layout(spec, engine)
    assert result["profile"] == "expanded"
    assert result["x_rotation_deg"] in (60, 90)
    assert result["annotation_font_pt"] >= 10
    assert result["cell_size_in"] > plan_layout(concrete(False), engine)["cell_size_in"]
    assert result["max_annotation_width_in"] + 0.20 < result["cell_size_in"]
    assert result == plan_layout(spec, engine)
    for row, column, expected in [
        (0, 8, 0.4978319193241571),
        (3, 4, -0.65753290762845),
        (4, 8, 0.36607882718852036),
        (7, 8, 0.32887300077998355),
    ]:
        assert spec.correlation_matrix[row][column] == pytest.approx(expected, abs=1e-13)


def test_estimator_and_rotation_depend_on_width_not_character_count():
    assert text_width_inches("WWWW", 10) > text_width_inches("iiii", 10)
    results = []
    for label in ("iiiiiiii", "MMMM", "MMMMMMMMMMMMMMMMMMMMMMMM"):
        labels = [label, "Other"]
        results.append(plan_layout(CorrelationHeatmapSpec(labels, [[1, 0], [0, 1]]), "origin"))
    assert [r["x_rotation_deg"] for r in results] == [45, 60, 90]


def test_native_layout_verification_rejects_missing_and_wrong_properties():
    result = plan_layout(concrete(), "origin")
    assert not verify_layout(result, {})
    actual = {
        key: result[key]
        for key in ("page_width_in", "page_height_in", "plot_left_in", "plot_bottom_in", "plot_span_in")
    }
    actual.update(
        plot_height_in=result["plot_span_in"],
        x_label_font_pt=[10] * 9,
        y_label_font_pt=[10] * 9,
        x_label_rotation_deg=[result["x_rotation_deg"]] * 9,
        annotation_font_pt=[11] * 81,
    )
    assert verify_layout(result, {"engine": "origin", "layout": actual})
    actual["annotation_font_pt"][0] = 9
    assert not verify_layout(result, {"layout": actual})
    actual["annotation_font_pt"][0] = float("nan")
    assert not verify_layout(result, {"engine": "origin", "layout": actual})


def test_canonical_plan_freezes_layout_and_rejects_stale_geometry(tmp_path):
    sys.path.insert(0, str(ROOT / "skill/editaplot/scripts"))
    import editaplot_core as core
    from editaplot_engine.correlation_layout import layouts
    from editaplot_engine.workflow import preview

    spec = concrete()
    source = FIXTURES / "concrete_correlation.csv"
    mapping = {"assignments": {"Variable": "category", **{s: "series" for s in spec.labels}}}
    proposal = preview(
        source,
        tmp_path / "preview",
        template_id="heatmap",
        mapping=mapping,
        correlation_heatmap_spec=spec.to_dict(),
        engine_home=ROOT / "runtime",
    )
    plan = core.build_plan(
        source,
        template_id="heatmap",
        claim="Display supplied correlations and p-values",
        evidence_role="relationship",
        mapping=mapping,
        correlation_heatmap_spec=spec.to_dict(),
        semantic_confirmation=proposal["understanding"]["confirmation_gate"]["confirmation_payload_template"],
        engine_home=ROOT / "runtime",
    )
    assert plan["correlation_layout"] == layouts(spec)
    core.validate_plan(plan)
    plan["correlation_layout"]["origin"]["annotation_font_pt"] = 9
    with pytest.raises(core.EditaPlotError, match="Frozen correlation layout"):
        core._validate_correlation_heatmap_plan(plan)
