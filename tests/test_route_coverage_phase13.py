"""Registry coverage and Batch 1 native XY route composition."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "runtime" / "src", ROOT / "skill" / "editaplot" / "scripts", ROOT):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import editaplot_core as core  # noqa: E402
from editaplot_engine.models import EngineError  # noqa: E402
from grapher_sciplot.engine import SUPPORTED_TEMPLATE_ROUTES, GrapherEngine  # noqa: E402

from tools.build_route_coverage import build  # noqa: E402

BATCH = ("cv", "lsv", "xas")


def _plan(template: str, output: Path) -> tuple[dict, Path]:
    source = ROOT / "runtime" / "templates" / template / "example_standard.csv"
    understanding = core.understand_data(source, template_id=template, engine_home=ROOT / "runtime")
    plan = core.build_plan(
        source, template_id=template, claim=f"{template} source series remain editable.",
        evidence_role="relationship",
        semantic_confirmation=understanding["confirmation_gate"]["confirmation_payload_template"],
        engine_home=ROOT / "runtime",
    )
    output.mkdir(parents=True, exist_ok=True)
    path = output / "render-plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan, path


def test_route_inventory_matches_registry_and_dispatch() -> None:
    inventory = build()
    saved = json.loads((ROOT / "docs" / "route-coverage-phase13.json").read_text(encoding="utf-8"))
    assert inventory == saved
    assert inventory["route_count"] == 41
    assert inventory["category_counts"] == {"A": 7, "B": 14, "C": 20}
    supported = {row["route_id"] for row in inventory["routes"]
                 if row["grapher_status"] == "supported"}
    assert supported == set(SUPPORTED_TEMPLATE_ROUTES)
    assert inventory["grapher_supported_count"] == 7
    assert inventory["batch_1"] == sorted(BATCH)
    assert inventory["capability_limitations"][0]["error_code"] == "unsupported_fit_weighting"


@pytest.mark.parametrize("route", BATCH)
def test_batch_1_reuses_xy_line_without_dropping_semantics(route: str, tmp_path: Path) -> None:
    plan, _path = _plan(route, tmp_path)
    data = plan["render_spec"]["data"]
    assert plan["render_spec"]["chart_type"] == "xy_line"
    assert len(data["y"]) == 2 and "y_errors" not in data
    spec, frame = GrapherEngine()._prepare(plan)
    assert spec["chart_type"] == "xy_line"
    assert list(frame) == [data["x"], *data["y"]]
    blocked = json.loads(json.dumps(plan))
    blocked["template"]["id"] = "heatmap"
    with pytest.raises(EngineError) as error:
        GrapherEngine()._prepare(blocked)
    assert error.value.code == "grapher_route_unsupported"


@pytest.mark.grapher
@pytest.mark.skipif(os.name != "nt", reason="Grapher COM requires Windows")
@pytest.mark.parametrize("route", BATCH)
def test_batch_1_grapher_native_route(route: str, tmp_path: Path) -> None:
    pytest.importorskip("pythoncom")
    from grapher_sciplot.smoke import SmokeFailure, discover

    try:
        discover()
    except SmokeFailure as exc:
        pytest.skip(str(exc))
    plan, plan_file = _plan(route, tmp_path)
    output = tmp_path / route
    engine = GrapherEngine()
    rendered = engine.render(plan, plan_file=plan_file, output_dir=output)
    verified = engine.verify(output)
    assert rendered.status == verified["status"] == "ok"
    assert verified["checks"]["document_reopened"]
    assert verified["checks"]["plot_binding"]
    assert len(verified["readback"]["plots"]) == 2
    for suffix in ("grf", "png", "pdf"):
        assert (output / f"result.{suffix}").is_file()
    # COM proxy release can complete after this pytest process exits. The
    # isolated runner checks newly remaining PIDs at that job boundary.


@pytest.mark.origin
@pytest.mark.skipif(os.name != "nt", reason="Origin automation requires Windows")
@pytest.mark.parametrize("route", BATCH)
def test_batch_1_origin_baseline(route: str, tmp_path: Path) -> None:
    pytest.importorskip("originpro")
    if not core.discover_origin_application()["launch_registration_detected"]:
        pytest.skip("Origin isolated COM registration is unavailable")
    from editaplot_engine.origin import OriginEngine

    plan, plan_file = _plan(route, tmp_path)
    output = tmp_path / route
    engine = OriginEngine()
    rendered = engine.render(
        plan, plan_file=plan_file, engine_home=ROOT / "runtime",
        python_executable=sys.executable, output_dir=output,
    )
    assert rendered.status == engine.verify(output)["status"] == "ok"
    for suffix in ("opju", "png", "pdf", "tif"):
        assert (output / f"result.{suffix}").is_file()
