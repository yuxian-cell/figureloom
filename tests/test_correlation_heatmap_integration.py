"""Canonical workflow -> native correlation Heatmap -> reopen/readback/verify."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "runtime" / "src", ROOT / "skill" / "figureloom" / "scripts"):
    sys.path.insert(0, str(path))

from figureloom_engine.correlation_heatmap import CorrelationHeatmapSpec, verify_readback  # noqa: E402
from figureloom_engine.workflow import preview, render_confirmed  # noqa: E402


def fixture(tmp_path: Path, size: int = 8, *, pvalues: bool = True):
    labels = tuple(f"Demo_{index + 1}" for index in range(size))
    # Signed AR(1) correlation matrix: deterministic positive-definite fixture.
    matrix = [
        [(-1) ** (row + column) * 0.73 ** abs(row - column) for column in range(size)] for row in range(size)
    ]
    probabilities = (
        [
            [
                1.0 if row == column else (0.0005, 0.005, 0.025, 0.2)[(row + column) % 4]
                for column in range(size)
            ]
            for row in range(size)
        ]
        if pvalues
        else None
    )
    spec = CorrelationHeatmapSpec(
        labels, matrix, probabilities, significance_enabled=pvalues, title="Synthetic correlation example"
    )
    source = tmp_path / "demo_correlation.csv"
    with source.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Label", *labels])
        writer.writerows([labels[index], *row] for index, row in enumerate(matrix))
    return source, spec


@pytest.mark.parametrize("engine", ["origin", "grapher"])
def test_correlation_workflow_preview(tmp_path, engine):
    source, spec = fixture(tmp_path)
    result = preview(
        source,
        tmp_path / "workflow",
        engine_name=engine,
        template_id="heatmap",
        correlation_heatmap_spec=spec.to_dict(),
        engine_home=ROOT / "runtime",
    )
    assert result["correlation_heatmap_spec"] == spec.to_dict()
    assert result["understanding"]["confirmation_gate"]["can_confirm_now"]


def _native_workflow(tmp_path, engine):
    source, spec = fixture(tmp_path)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    workspace = tmp_path / engine
    preview(
        source,
        workspace,
        engine_name=engine,
        template_id="heatmap",
        correlation_heatmap_spec=spec.to_dict(),
        engine_home=ROOT / "runtime",
    )
    session = render_confirmed(
        workspace / "workflow-preview.json",
        confirmed=True,
        claim="Explicitly synthetic correlation matrix for layout and mapping tests.",
    )
    assert session["status"] == "verified"
    native = session["current_readback"]
    assert all(verify_readback(spec, native).values())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    plan = json.loads((workspace / "render-plan.json").read_text(encoding="utf-8"))
    assert plan["render_spec"]["chart_type"] == "correlation_heatmap"
    _verify_native_mutation(tmp_path, engine, spec, Path(session["artifacts"]["editable"]))
    return session


def _verify_native_mutation(tmp_path, engine, spec, path):
    """Change the saved native object, leaving the confirmed source and plan intact."""
    if engine == "origin":
        from origin_sciplot.origin_backend.correlation_heatmap import GRAPH_NAME, read
        from origin_sciplot.origin_backend.session import OriginSession

        changed = tmp_path / "changed.opju"
        with OriginSession(keep_open=False) as session:
            op = session.op
            assert op.open(str(path), asksave=False)
            layer = op.find_graph(GRAPH_NAME)[0]
            matrix = op.find_sheet("m", layer.plot_list()[0].obj.GetDatasetName())
            values = matrix.to_np2d()
            values[0, 1] = -0.2
            matrix.from_np(values)
            layer.label("CHC0X1").text = "changed"
            layer.set_int("cmap.color1", op.ocolor((255, 0, 0)))
            op.save(str(changed))
            op.new(asksave=False)
            native = read(op, changed)
        assert not verify_readback(spec, native)["matrix_values"]
    else:
        from grapher_sciplot.correlation_heatmap import GRAPH_NAME, read
        from grapher_sciplot.engine import _application
        from grapher_sciplot.smoke import call, get, put

        changed = tmp_path / "changed.grf"
        with _application(visible=False) as (app, _info):
            document = call(get(app, "Documents"), "Open", str(path))
            try:
                shapes = get(document, "Shapes")
                graph = call(shapes, "Item", GRAPH_NAME)
                plot = call(get(graph, "Plots"), "Item", 1)
                put(get(call(plot, "ClassSymbol", 1), "Fill"), "foreColor", 255)
                put(call(shapes, "Item", "CH_CELL_0_1"), "text", "changed")
                call(document, "SaveAs", str(changed))
            finally:
                call(document, "Close", False)
            native = read(app, changed)
    checks = verify_readback(spec, native)
    assert not checks["annotations"]
    assert not checks["color_mapping"]


@pytest.mark.origin
def test_origin_native_correlation_heatmap(tmp_path):
    import figureloom_core

    pytest.importorskip("originpro")
    if not figureloom_core.discover_origin_application()["launch_registration_detected"]:
        pytest.skip("Origin is unavailable")
    _native_workflow(tmp_path, "origin")


@pytest.mark.grapher
def test_grapher_native_correlation_heatmap(tmp_path):
    from grapher_sciplot.smoke import SmokeFailure, discover

    try:
        discover()
    except SmokeFailure as exc:
        pytest.skip(str(exc))
    _native_workflow(tmp_path, "grapher")
