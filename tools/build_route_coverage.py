"""Generate Phase 13 route inventory from public implemented template manifests."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "src"))

from grapher_sciplot.engine import SUPPORTED_TEMPLATE_ROUTES  # noqa: E402
from origin_sciplot.scientific_workflow import prepare_scientific  # noqa: E402
from origin_sciplot.template_registry import TemplateRegistry  # noqa: E402

A = {"bar", "cv", "line_error", "lsv", "scatter", "trend", "xas"}
B = {
    "bland_altman", "calibration_curve", "decision_curve", "diagnostic_curve",
    "dsc", "eis", "ftir", "horizontal_bar", "nmr", "paired_trajectory",
    "percent_stacked_bar", "pl", "stacked_bar", "xps_compare",
}
C = {
    "bubble", "circular_network", "confusion_matrix", "density_ridgeline3d",
    "forest", "grouped_box", "heatmap", "histogram", "pie", "radar",
    "raincloud", "raw_summary", "sankey", "shap_dashboard", "shap_summary",
    "trajectory3d", "uv_vis", "violin", "xps", "xrd",
}
SUPPORTED = set(SUPPORTED_TEMPLATE_ROUTES)
BATCH_1 = {"cv", "lsv", "xas"}
HIGH_PRIORITY = {"scatter", "trend", "line_error", "bar", "cv", "lsv", "xas", "eis", "pl", "uv_vis"}


def _runner(manifest: object) -> str:
    if manifest.renderer_adapters:
        return " | ".join(sorted(manifest.renderer_adapters.values()))
    tree = ast.parse(manifest.runner_path.read_text(encoding="utf-8"))
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
               and node.module and node.module.startswith("origin_sciplot.origin_backend.")]
    return imports[0].rsplit(".", 1)[-1] if imports else "unresolved"


def _tests(template_id: str) -> list[str]:
    pattern = re.compile(rf"(?<![\w]){re.escape(template_id)}(?![\w])")
    specific = [str(path.relative_to(ROOT)).replace("\\", "/")
                for path in sorted((ROOT / "tests").glob("test_*.py"))
                if pattern.search(path.read_text(encoding="utf-8"))]
    return sorted(set(["tests/test_public_template_alignment.py", *specific]))


def build() -> dict[str, object]:
    manifests = TemplateRegistry(ROOT / "runtime" / "templates").implemented()
    ids = {manifest.id for manifest in manifests}
    if ids != A | B | C or len(A) + len(B) + len(C) != len(ids):
        raise ValueError(
            f"Route annotations differ from registry: missing={ids - A - B - C}, "
            f"stale={(A | B | C) - ids}"
        )
    if not SUPPORTED <= ids or not HIGH_PRIORITY <= ids or not BATCH_1 <= A:
        raise ValueError("Coverage and batch annotations must reference public registry routes")
    routes = []
    for manifest in sorted(manifests, key=lambda item: item.id):
        examples = []
        for example in manifest.examples:
            item = {"id": example.id, "fixture": str(example.path.relative_to(ROOT)).replace("\\", "/")}
            if manifest.workflow == "scientific_table":
                preparation = prepare_scientific(example.path, manifest.id)
                spec = preparation.plot_spec
                item.update({"plot_kind": spec.plot_kind, "plot_mode": spec.plot_mode,
                             "series_count": len(spec.series),
                             "error_series_count": sum(bool(series.error_column) for series in spec.series),
                             "x_scale": spec.x_scale, "y_scale": spec.y_scale,
                             "descending_x": (spec.axis_plan.x_from > spec.axis_plan.x_to
                                              if spec.axis_plan.x_from is not None
                                              and spec.axis_plan.x_to is not None else False),
                             "inset": bool(spec.inset_series)})
            examples.append(item)
        category = "A" if manifest.id in A else "B" if manifest.id in B else "C"
        status = ("supported" if manifest.id in SUPPORTED else
                  "new_family_required" if category == "C" else "not_implemented")
        capabilities = sorted({
            "xy_line" if item.get("plot_kind") == "line" else
            "xy_line" if item.get("plot_kind") == "line_error" else
            "xy_scatter" if item.get("plot_kind") == "scatter" else
            "bar" if item.get("plot_kind") == "bar_error" else
            str(item.get("plot_kind", "xps_native_analysis"))
            for item in examples
        })
        if any(item.get("error_series_count") for item in examples):
            capabilities.append("symmetric_y_error")
        if any(item.get("descending_x") for item in examples):
            capabilities.append("descending_x_axis")
        if any(item.get("inset") for item in examples):
            capabilities.append("inset_layer")
        semantics = sorted({f"plot_mode:{item['plot_mode']}" for item in examples if "plot_mode" in item})
        if any(item.get("error_series_count") for item in examples):
            semantics.append("independent_symmetric_y_error_columns")
        if any(item.get("descending_x") for item in examples):
            semantics.append("descending_x_axis")
        routes.append({
            "route_id": manifest.id, "template_id": manifest.id,
            "family": manifest.family, "origin_renderer": _runner(manifest),
            "workflow": manifest.workflow, "category": category,
            "required_capabilities": capabilities, "required_semantics": semantics,
            "examples": examples,
            "current_tests": _tests(manifest.id), "origin_support": "supported",
            "grapher_status": status, "native_editable": status == "supported",
            "save_reopen": status == "supported", "readback": status == "supported",
            "verify": status == "supported", "gui_checked": manifest.id in SUPPORTED - BATCH_1,
            "gui_representative": "phase10_xy_multiline" if manifest.id in BATCH_1 else None,
            "migration_group": "batch_1" if manifest.id in BATCH_1 else None,
        })
        if manifest.id == "heatmap":
            routes[-1]["submodes"] = {
                "correlation_heatmap": {
                    "origin": "native_matrix_heatmap",
                    "grapher": "native_class_scatter_21_intervals",
                    "save_reopen": True, "native_readback": True, "verify": True,
                    "gui_checked": True,
                    "gui_checked_engines": {"origin": True, "grapher": True},
                    "spec_required": "CorrelationHeatmapSpec",
                    "generic_grapher_heatmap_supported": False,
                }
            }
    return {
        "schema_version": "1.0", "source": "TemplateRegistry.public implemented manifests",
        "route_count": len(routes), "category_counts": {name: sum(row["category"] == name for row in routes)
                                                for name in ("A", "B", "C")},
        "grapher_supported_count": sum(row["grapher_status"] == "supported" for row in routes),
        "raw_coverage": len(SUPPORTED) / len(routes),
        "mvp_high_priority_routes": sorted(HIGH_PRIORITY),
        "mvp_high_priority_coverage": len(HIGH_PRIORITY & SUPPORTED) / len(HIGH_PRIORITY),
        "batch_1": sorted(BATCH_1), "routes": routes,
        "capability_limitations": [{"route_id": "scatter#explicit_weighted_linear_fit",
                                    "origin_status": "supported",
                                    "grapher_status": "unsupported_backend_capability",
                                    "error_code": "unsupported_fit_weighting"}],
    }


if __name__ == "__main__":
    target = ROOT / "docs" / "route-coverage-phase13.json"
    target.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)
