"""Small resumable workflow built from the existing EditaPlot contracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import EngineError
from .registry import get_engine


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise EngineError("output_unwritable", "The workflow directory cannot be written.") from exc


def _read_record(path: Path, kind: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EngineError(f"{kind}_not_found", f"{kind.title()} file does not exist.") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EngineError(f"{kind}_invalid", f"{kind.title()} file is unreadable or invalid JSON.") from exc
    if not isinstance(value, dict):
        raise EngineError(f"{kind}_invalid", f"{kind.title()} must be a JSON object.")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(root: Path, session: dict[str, Any], stage: str, error: Exception | None = None) -> None:
    event: dict[str, Any] = {"at": _now(), "run_id": session.get("run_id"),
                             "engine": session.get("engine"),
                             "route": session.get("recommendation", {}).get("selected_template_id"),
                             "native_version": session.get("native_version"), "stage": stage}
    if error is not None:
        event["error_code"] = getattr(error, "code", type(error).__name__)
        if os.environ.get("EDITAPLOT_VERBOSE") == "1":
            event["native_trace"] = "".join(traceback.format_exception(error))
    try:
        with (root / "runtime.log").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        pass  # Logging cannot replace the native operation's primary result.


def _source_for_sheet(source: Path, sheet: str | None, workspace: Path) -> tuple[Path, str | None, list[str]]:
    if source.suffix.lower() != ".xlsx":
        if sheet is not None:
            raise EngineError("sheet_unsupported", "Sheet selection requires XLSX input.")
        return source, None, []
    import pandas as pd

    with pd.ExcelFile(source, engine="openpyxl") as book:
        names = list(book.sheet_names)
        if sheet is None:
            return source, None, names
        if sheet not in names:
            raise EngineError(
                "sheet_not_found", f"Worksheet {sheet!r} is not in this workbook.", sheets=names
            )
        from origin_sciplot.data_loader import _frame_from_excel_matrix

        matrix = pd.read_excel(book, sheet_name=sheet, header=None, dtype=object)
        resolved = _frame_from_excel_matrix(matrix)
        if resolved is None:
            raise EngineError("no_data_rows", "The selected worksheet has no table.")
        frame, _ignored = resolved
        materialized = workspace / "selected_sheet.csv"
        frame.to_csv(materialized, index=False, encoding="utf-8-sig")
        return materialized, sheet, names


def _role_candidates(columns: list[dict[str, Any]]) -> dict[str, list[str]]:
    numeric = [item["name"] for item in columns if item["kind"] == "numeric"]
    error = [item["name"] for item in columns if "error" in item["semantic_tags"]]
    x = [item["name"] for item in columns if "x" in item["semantic_tags"]]
    return {
        "x": x or numeric[:1],
        "y": [name for name in numeric if name not in set(x or numeric[:1]) | set(error)],
        "error": error,
        "group": [item["name"] for item in columns if item["kind"] == "categorical"],
    }


def preview(
    source_file: str | Path,
    workspace: str | Path,
    *,
    engine_name: str = "origin",
    template_id: str | None = None,
    sheet: str | None = None,
    intent: str = "",
    mapping: dict[str, Any] | None = None,
    fit_spec: dict[str, Any] | list[dict[str, Any]] | None = None,
    engine_home: str | Path | None = None,
) -> dict[str, Any]:
    import editaplot_core as core

    from editaplot_engine.fit_contract import FitSpec

    engine = get_engine(engine_name)
    if isinstance(fit_spec, dict):
        fit_spec = FitSpec.from_dict(fit_spec).to_dict()
    elif isinstance(fit_spec, list):
        fit_spec = [FitSpec.from_dict(item).to_dict() for item in fit_spec]
    source = Path(source_file).expanduser().resolve()
    if not source.is_file():
        raise EngineError("file_not_found", "Source table does not exist.")
    root = Path(workspace).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise EngineError("output_unwritable", "The workflow directory cannot be created.") from exc
    preview_path = root / "workflow-preview.json"
    if preview_path.exists() or (root / "session.json").exists():
        raise EngineError("workspace_exists", "This workspace already contains a workflow.")
    before = _hash(source)
    effective, selected_sheet, sheets = _source_for_sheet(source, sheet, root)
    inspection = core.inspect_data(effective, engine_home=engine_home)
    recommendation = core.recommend_charts(effective, intent=intent, limit=41, engine_home=engine_home)
    if engine.name == "grapher":
        from grapher_sciplot.engine import SUPPORTED_TEMPLATE_ROUTES

        supported = set(SUPPORTED_TEMPLATE_ROUTES)
        candidates = [item for item in recommendation["candidates"] if item["template_id"] in supported]
    else:
        candidates = recommendation["candidates"]
    chosen = template_id or (candidates[0]["template_id"] if candidates else None)
    roles = _role_candidates(inspection["columns"])
    if template_id is None and fit_spec is None and chosen == "scatter" and len(roles["y"]) >= 2:
        trend = next((item for item in candidates if item["template_id"] == "trend"), None)
        if trend is not None and trend["score"] >= candidates[0]["score"] - 0.05:
            chosen = "trend"
    if chosen is None or chosen not in {item["template_id"] for item in candidates}:
        raise EngineError(
            "unsupported_backend_capability",
            "No compatible recommendation for the selected engine and data.",
            engine=engine.name,
            requested_template=chosen,
        )
    understanding = core.understand_data(
        effective, template_id=chosen, mapping=mapping, engine_home=engine_home
    )
    if _hash(source) != before:
        raise EngineError("source_changed_during_preview", "Source changed during inspection.")
    result = {
        "schema_version": "1.0",
        "status": "awaiting_confirmation",
        "created_at": _now(),
        "engine": engine.name,
        "source": {"path": str(source), "sha256": before, "type": source.suffix.lower().lstrip("."),
                   "selected_sheet": selected_sheet, "sheets": sheets},
        "effective_source": {"path": str(effective), "sha256": _hash(effective)},
        "dataset_profile": {"table": inspection["table"], "columns": inspection["columns"],
                            "role_candidates": roles},
        "recommendation": {"candidates": candidates[:3], "selected_template_id": chosen},
        "understanding": understanding,
        "mapping": mapping,
        "fit_spec": fit_spec,
        "intent": intent,
        "engine_home": str(engine_home) if engine_home else None,
    }
    _write(preview_path, result)
    return result


def render_confirmed(preview_file: str | Path, *, claim: str, confirmed: bool = False) -> dict[str, Any]:
    import editaplot_core as core

    if not confirmed:
        raise EngineError("confirmation_required", "Confirm the preview before rendering.")
    preview_path = Path(preview_file).expanduser().resolve()
    session_file = preview_path.parent / "session.json"
    if session_file.exists():
        existing = _read_record(session_file, "session")
        if existing.get("status") in {"rendering", "editing"}:
            raise EngineError("incomplete_session", "A previous workflow job was interrupted.")
        raise EngineError("session_exists", "This workflow has already rendered a session.")
    data = _read_record(preview_path, "preview")
    if data["status"] != "awaiting_confirmation":
        raise EngineError("confirmation_required", "A workflow preview must be confirmed first.")
    source = Path(data["source"]["path"])
    effective = Path(data["effective_source"]["path"])
    if not source.is_file() or _hash(source) != data["source"]["sha256"]:
        raise EngineError("source_changed_since_preview", "Source changed after preview; inspect it again.")
    if not effective.is_file() or _hash(effective) != data["effective_source"]["sha256"]:
        raise EngineError("staging_changed_since_preview", "Selected-sheet staging changed.")
    understanding = data["understanding"]
    if not understanding["confirmation_gate"]["can_confirm_now"]:
        raise EngineError("semantic_confirmation_required", "Resolve uncertain columns before rendering.")
    plan = core.build_plan(
        effective,
        template_id=data["recommendation"]["selected_template_id"],
        claim=claim,
        evidence_role="relationship",
        intent=data["intent"],
        mapping=data["mapping"],
        fit_spec=data["fit_spec"],
        semantic_confirmation=understanding["confirmation_gate"]["confirmation_payload_template"],
        engine_home=data["engine_home"],
    )
    root = preview_path.parent
    plan_file = root / "render-plan.json"
    _write(plan_file, plan)
    engine = get_engine(data["engine"])
    session = {
        "schema_version": "1.0", "status": "rendering", "run_id": uuid.uuid4().hex,
        "created_at": _now(), "engine": engine.name,
        "source": data["source"], "effective_source": data["effective_source"],
        "recommendation": data["recommendation"],
        "confirmation": {"claim": claim, "proposal_hash": understanding["understanding"]["proposal_hash"]},
        "plan": {"path": str(plan_file), "hash": plan["plan_hash"]},
        "artifacts": None, "current_readback": None,
        "verification": {"status": "not_run"}, "edits": [],
    }
    _write(session_file, session)
    _log(root, session, "rendering")
    try:
        availability = engine.doctor(engine_home=data["engine_home"])
        if not availability["ready_for_render"]:
            raise EngineError(f"{engine.name}_unavailable", "The selected native application is unavailable.",
                              engine=engine.name, doctor=availability)
        result = engine.render(
            plan,
            plan_file=plan_file,
            engine_home=data["engine_home"],
            python_executable=sys.executable,
            output_dir=root / engine.name,
            close_application=True,
        )
        if result.status != "ok":
            raise EngineError("native_render_failed", "The native engine did not complete rendering.",
                              engine=engine.name)
        session["native_version"] = result.metadata.get("engine_version")
        _log(root, session, "native_render_returned")
        verified = engine.verify(result.output_dir)
        if verified["status"] != "ok":
            raise EngineError("verify_failed", "Native result failed verification.", engine=engine.name)
        if not result.editable_path.is_file() or any(
            not path.is_file() for path in result.exports.values()
        ):
            raise EngineError("artifact_not_found", "A verified native artifact is missing.",
                              engine=engine.name)
        if _hash(source) != data["source"]["sha256"]:
            raise EngineError("source_changed_during_render", "Source changed during rendering.")
    except EngineError as exc:
        _log(root, session, "render_failed", exc)
        session["status"] = "failed"
        session["error"] = {"code": exc.code, "message": str(exc)}
        session["verification"] = {"status": "failed"}
        _write(session_file, session)
        if exc.code == "unsupported_fit_weighting":
            raise EngineError(
                exc.code, str(exc), engine=engine.name, **exc.details,
                suggested_action="Use Origin, or explicitly remove weighting after scientific review.",
            ) from exc
        raise
    except Exception as exc:
        _log(root, session, "render_failed", exc)
        failure = EngineError("native_render_failed", "Native rendering or verification failed.",
                              engine=engine.name)
        session["status"] = "failed"
        session["error"] = {"code": failure.code, "message": str(failure)}
        session["verification"] = {"status": "failed"}
        _write(session_file, session)
        raise failure from exc
    session.update(status="verified", artifacts=result.to_dict(), current_readback=result.readback,
                   verification={"status": verified["status"]})
    _write(session_file, session)
    _log(root, session, "verified")
    return session


def normalize_edit(operation: str, *, value: str, axis: str | None = None,
                   series: str | None = None) -> dict[str, str]:
    if operation == "set_axis_title" and axis in {"x", "y"} and value.strip():
        return {"operation": operation, "axis": axis, "value": value.strip()}
    if operation == "set_line_style" and series and value in {"solid", "dashed"}:
        return {"operation": operation, "series": series, "value": value}
    raise EngineError("edit_unsupported", "Edit must be an axis title or named-series line style.")


def parse_edit_phrase(phrase: str) -> dict[str, str]:
    """Interpret only two explicit user phrases; an AI may supply the same structured plan."""
    line = re.fullmatch(r"(?:把\s*)?(.+?)\s*(?:改成|设为)\s*虚线", phrase.strip())
    if line:
        return normalize_edit("set_line_style", series=line.group(1), value="dashed")
    axis = re.fullmatch(r"(?:把\s*)?([XYxy])\s*轴标题\s*(?:改成|设为)\s*(.+)", phrase.strip())
    if axis:
        return normalize_edit("set_axis_title", axis=axis.group(1).lower(), value=axis.group(2))
    raise EngineError("edit_unsupported", "This edit phrase is outside the supported allowlist.")


def edit_session(session_file: str | Path, edit: dict[str, str], *, request: str = "") -> dict[str, Any]:
    edit = normalize_edit(
        edit.get("operation", ""), value=edit.get("value", ""),
        axis=edit.get("axis"), series=edit.get("series"),
    )
    path = Path(session_file).expanduser().resolve()
    session = _read_record(path, "session")
    if session["status"] in {"rendering", "editing"}:
        raise EngineError("incomplete_session", "A previous workflow job was interrupted.")
    if session["status"] != "verified":
        raise EngineError("session_not_verified", "Only a verified session can be edited.")
    artifact = Path(session["artifacts"]["editable"])
    if not artifact.is_file():
        raise EngineError("artifact_not_found", "The session's native project is missing.")
    source = Path(session["source"]["path"])
    if not source.is_file() or _hash(source) != session["source"]["sha256"]:
        raise EngineError("source_changed_since_render", "The source changed; rerender explicitly.")
    engine = get_engine(session["engine"])
    if engine.name == "origin" and edit["operation"] != "set_axis_title":
        raise EngineError("edit_unsupported", "Origin line-style editing is not verified.", engine="origin")
    session["status"] = "editing"
    _write(path, session)
    _log(path.parent, session, "editing")
    try:
        outcome = engine.apply_edit(artifact, edit)
        if outcome.get("status") != "ok":
            raise EngineError("edit_verify_failed", "The native edit failed verification.",
                              engine=engine.name)
        exports = session["artifacts"]["exports"]
        if any(not Path(export).is_file() for export in exports.values()):
            raise EngineError("edit_verify_failed", "An edited native export is missing.", engine=engine.name)
    except Exception as exc:
        _log(path.parent, session, "edit_failed", exc)
        failure = exc if isinstance(exc, EngineError) else EngineError(
            "native_edit_failed", "The native edit failed; inspect the project before retrying.",
            engine=engine.name,
        )
        session["status"] = "edit_failed"
        session["edits"].append({"request": request, "edit_plan": edit, "attempted_at": _now(),
                                 "status": "failed", "error": {"code": failure.code,
                                                                "message": str(failure)}})
        session["verification"] = {"status": "failed", "operation": edit["operation"]}
        _write(path, session)
        if failure is exc:
            raise
        raise failure from exc
    session["edits"].append({"request": request, "edit_plan": edit, "applied_at": _now(),
                             "verification": {"status": outcome["status"], "actual": outcome["actual"]}})
    session["status"] = "verified"
    session["current_readback"] = outcome.get("readback", outcome)
    session["verification"] = {"status": outcome["status"], "operation": edit["operation"]}
    _write(path, session)
    _log(path.parent, session, "edit_verified")
    return {"status": "ok", "session": str(path), "edit": edit, "native": outcome}
