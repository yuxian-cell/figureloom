"""Delivery and reopened verification for the existing Heatmap correlation submode."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .correlation_heatmap import (
    RECOMMENDED_MAX_SIZE,
    CorrelationHeatmapSpec,
    validate_source,
    verify_readback,
)
from .correlation_layout import plan_layout, verify_layout
from .models import EngineError, RenderResult


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _verification_code(checks: dict[str, bool]) -> str:
    if not checks.get("color_mapping", True) or not checks.get("linked_color_legend", True):
        return "color_mapping_mismatch"
    if not checks.get("annotations", True):
        return "annotation_mismatch"
    return "heatmap_verify_failed"


def is_correlation_project(path: Path) -> bool:
    manifest = path.parent / "manifest.json"
    return (
        manifest.is_file()
        and json.loads(manifest.read_text(encoding="utf-8")).get("family") == "correlation_heatmap"
    )


def readback(engine: str, path: Path) -> dict[str, Any]:
    if engine not in ("origin", "grapher"):
        raise EngineError(
            "heatmap_unsupported_by_engine", "Engine has no native correlation heatmap adapter."
        )
    if engine == "origin":
        from origin_sciplot.origin_backend.correlation_heatmap import read
        from origin_sciplot.origin_backend.session import OriginSession

        with OriginSession(keep_open=False) as session:
            return read(session.op, path)
    from grapher_sciplot.correlation_heatmap import read
    from grapher_sciplot.engine import _application

    with _application(visible=False) as (app, _info):
        return read(app, path)


def render(
    engine: str, plan: dict[str, Any], plan_file: str | Path, output_dir: str | Path | None
) -> RenderResult:
    import editaplot_core
    from origin_sciplot.output_manager import _claim_unique_output_dir, default_output_dir

    if engine not in ("origin", "grapher"):
        raise EngineError(
            "heatmap_unsupported_by_engine", "Engine has no native correlation heatmap adapter."
        )

    editaplot_core.validate_plan(plan)
    spec = CorrelationHeatmapSpec.from_dict(plan["correlation_heatmap"])
    layout = plan.get("correlation_layout", {}).get(engine) or plan_layout(spec, engine)
    warnings = (
        ["Dense annotation layout: recommended maximum is 10 labels; inspect native text before publication."]
        if len(spec.labels) > RECOMMENDED_MAX_SIZE
        else []
    )
    source = Path(plan["source"]["path"]).resolve()
    validate_source(spec, source)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_hash != plan["source"]["sha256"]:
        raise EngineError("source_changed_since_plan", "Source changed since the matrix was confirmed.")
    target = _claim_unique_output_dir(
        Path(output_dir).resolve() if output_dir else default_output_dir(source, "heatmap")
    )
    shutil.copy2(source, target / f"input_copy{source.suffix}")
    # Use the validated in-memory canonical plan, never a possibly different file's contents.
    _write(target / "render-plan.json", plan)
    suffixes = ("png", "pdf", "tif") if engine == "origin" else ("png", "pdf")
    try:
        if engine == "origin":
            from origin_sciplot.origin_backend.correlation_heatmap import create, read
            from origin_sciplot.origin_backend.session import OriginSession

            with OriginSession(keep_open=False) as session:
                path = create(session.op, spec, target, layout)
                native = read(session.op, path)
                version = session.environment.origin_version
        else:
            from grapher_sciplot.correlation_heatmap import create, read
            from grapher_sciplot.engine import _application

            with _application(visible=False) as (app, _info):
                path = create(app, spec, target, layout)
                native = read(app, path)
                version = _info["version"]
        checks = verify_readback(spec, native)
        checks["layout"] = verify_layout(layout, native)
        if not all(checks.values()):
            raise EngineError(
                _verification_code(checks),
                "Native Heatmap does not match the confirmed matrix.",
                checks=checks,
            )
        if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
            raise EngineError("source_changed_during_render", "Source changed during native rendering.")
        _write(
            target / "manifest.json",
            {
                "engine": engine,
                "family": "correlation_heatmap",
                "source_sha256": source_hash,
                "engine_version": version,
                "mapping_mode": native["mapping"]["mode"],
                "warnings": warnings,
            },
        )
        _write(
            target / f"{engine}_verify_report.json", {"status": "ok", "checks": checks, "readback": native}
        )
        return RenderResult(
            engine,
            "ok",
            target,
            path,
            {suffix: target / f"result.{suffix}" for suffix in suffixes},
            native,
            {
                "family": "correlation_heatmap",
                "mapping_mode": native["mapping"]["mode"],
                "engine_version": version,
                "warnings": warnings,
            },
        )
    except EngineError:
        raise
    except Exception as exc:
        raise EngineError(
            "heatmap_render_failed",
            "Native correlation Heatmap execution failed.",
            engine=engine,
            detail=str(exc),
        ) from exc


def verify(engine: str, target: Path) -> dict[str, Any]:
    plan = json.loads((target / "render-plan.json").read_text(encoding="utf-8"))
    spec = CorrelationHeatmapSpec.from_dict(plan["correlation_heatmap"])
    path = target / ("result.opju" if engine == "origin" else "result.grf")
    try:
        native = readback(engine, path)
        checks = verify_readback(spec, native)
        if "correlation_layout" in plan:
            checks["layout"] = verify_layout(plan["correlation_layout"][engine], native)
        signatures = {"png": b"\x89PNG\r\n\x1a\n", "pdf": b"%PDF"}
        checks["editable_project"] = path.is_file() and path.stat().st_size > 0
        for suffix, signature in signatures.items():
            exported = target / f"result.{suffix}"
            checks[f"{suffix}_export"] = exported.is_file() and exported.read_bytes().startswith(signature)
        if engine == "origin":
            exported = target / "result.tif"
            checks["tif_export"] = exported.is_file() and exported.read_bytes()[:4] in (
                b"II*\x00",
                b"MM\x00*",
            )
        report = {
            "status": "ok" if all(checks.values()) else "failed",
            "engine": engine,
            "checks": checks,
            "readback": native,
            "programmatic_pass": all(checks.values()),
        }
        if not all(checks.values()):
            report["error"] = {
                "code": _verification_code(checks),
                "message": "Native heatmap verification mismatch.",
            }
    except Exception as exc:
        report = {
            "status": "failed",
            "engine": engine,
            "error": {"code": "heatmap_verify_failed", "message": str(exc)},
        }
    _write(target / f"{engine}_verify_report.json", report)
    return report
