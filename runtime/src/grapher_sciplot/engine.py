"""Formal EditaPlot engine for one native Grapher XY scatter route."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from editaplot_engine.models import EngineError, RenderResult

from .smoke import (
    PROGID,
    call,
    discover,
    get,
    grapher_pids,
    put,
    quit_owned_application,
    require_file,
    run_smoke,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _default_output_dir(source: Path) -> Path:
    label = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", source.stem).strip(" ._") or "data"
    return source.parent / f"{label}_EditaPlot_{datetime.now():%Y%m%d_%H%M%S}"


def _claim_output(path: Path) -> Path:
    for candidate in (path, *(path.with_name(f"{path.name}_{index:02d}") for index in range(2, 1000))):
        try:
            candidate.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return candidate
    raise EngineError(
        "output_directory_name_exhausted",
        "EditaPlot could not allocate a unique delivery-folder name.",
        engine="grapher",
    )


def _color_value(value: str) -> int:
    text = value.lstrip("#")
    red, green, blue = (int(text[index : index + 2], 16) for index in (0, 2, 4))
    return red | (green << 8) | (blue << 16)


def _read_source(plan: dict[str, Any]) -> pd.DataFrame:
    source = Path(plan["source"]["path"])
    if source.suffix.casefold() in {".xlsx", ".xls"}:
        return pd.read_excel(source, sheet_name=plan["source"].get("sheet") or 0)
    if source.suffix.casefold() in {".csv", ".txt"}:
        error: Exception | None = None
        for encoding in ("utf-8-sig", "utf-16", "gb18030"):
            try:
                return pd.read_csv(source, sep=None, engine="python", encoding=encoding)
            except UnicodeError as exc:
                error = exc
        if error is not None:
            raise error
    raise ValueError(f"Unsupported source format: {source.suffix}")


@contextmanager
def _application(*, visible: bool) -> Iterator[tuple[Any, dict[str, Any]]]:
    try:
        import pythoncom
        from win32com.client import DispatchEx
    except ImportError as exc:
        raise EngineError(
            "grapher_com_activation_failed",
            "pywin32 is required for Grapher COM automation.",
            engine="grapher",
        ) from exc
    before = grapher_pids()
    app = None
    owns_app = False
    owned_pid: int | None = None
    pythoncom.CoInitialize()
    try:
        app = DispatchEx(PROGID)
        created = grapher_pids() - before
        if len(created) != 1:
            raise EngineError(
                "grapher_com_activation_failed",
                "COM did not create one isolated Grapher process.",
                engine="grapher",
            )
        owns_app = True
        owned_pid = created.pop()
        put(app, "Visible", visible)
        yield app, {
            **discover(),
            "version": str(get(app, "Version")),
            "visible": bool(get(app, "Visible")),
            "pid": owned_pid,
        }
    except EngineError:
        raise
    except Exception as exc:
        raise EngineError("grapher_com_activation_failed", str(exc), engine="grapher") from exc
    finally:
        cleanup_error = (
            quit_owned_application(app, owned_pid)
            if app is not None and owns_app and owned_pid is not None
            else None
        )
        app = None
        pythoncom.CoUninitialize()
        if cleanup_error is not None:
            raise EngineError("grapher_cleanup_failed", str(cleanup_error), engine="grapher")


def _optional_get(obj: Any, name: str) -> Any | None:
    try:
        return get(obj, name)
    except Exception:
        return None


class GrapherEngine:
    name = "grapher"

    def detect(self) -> dict[str, Any]:
        registration = discover()
        version = None
        if importlib.util.find_spec("win32api") is not None:
            import win32api

            info = win32api.GetFileVersionInfo(registration["executable"], "\\")
            most, least = info["FileVersionMS"], info["FileVersionLS"]
            version = ".".join(
                str(value)
                for value in (most >> 16, most & 0xFFFF, least >> 16, least & 0xFFFF)
            )
        return {**registration, "version": version}

    def doctor(self, *, engine_home: str | Path | None = None) -> dict[str, Any]:
        del engine_home
        try:
            detection = self.detect()
            automation_available = importlib.util.find_spec("pythoncom") is not None
            return {
                "status": "ok" if automation_available else "failed",
                "engine": self.name,
                "installed": True,
                "automation_available": automation_available,
                "version": detection["version"],
                "progid": detection["progid"],
                "executable": detection["executable"],
                "ready_for_analysis": True,
                "ready_for_render": automation_available,
            }
        except Exception as exc:
            code = getattr(exc, "code", "grapher_not_installed")
            return {
                "status": "failed",
                "engine": self.name,
                "installed": False,
                "automation_available": False,
                "version": None,
                "ready_for_analysis": True,
                "ready_for_render": False,
                "error": {"code": code, "message": str(exc)},
            }

    def smoke(
        self,
        output_dir: str | Path,
        *,
        engine_home: str | Path | None = None,
        python_executable: str | Path | None = None,
        visible: bool = True,
        keep_application_open: bool = False,
    ) -> dict[str, Any]:
        del engine_home, python_executable, keep_application_open
        return run_smoke(Path(output_dir), visible=visible)

    @staticmethod
    def _prepare(plan: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
        render_spec = plan.get("render_spec")
        if plan["template"]["id"] != "scatter" or not isinstance(render_spec, dict):
            raise EngineError(
                "grapher_route_unsupported",
                "Grapher currently supports only the confirmed scatter route.",
                engine="grapher",
                supported_templates=["scatter"],
            )
        if plan.get("reference_adaptation") is not None or plan.get("reference_style") is not None:
            raise EngineError(
                "grapher_reference_style_unsupported",
                "The first Grapher route does not yet support reference-style adaptation.",
                engine="grapher",
            )
        data = render_spec.get("data")
        if render_spec.get("chart_type") != "xy_scatter" or not isinstance(data, dict):
            raise EngineError(
                "grapher_route_unsupported",
                "The Grapher route requires chart_type=xy_scatter.",
                engine="grapher",
            )
        x_column = data.get("x")
        y_columns = data.get("y")
        if not isinstance(x_column, str) or not isinstance(y_columns, list) or len(y_columns) != 1:
            raise EngineError(
                "grapher_route_unsupported",
                "The first Grapher route requires one X column and one Y series.",
                engine="grapher",
            )
        try:
            frame = _read_source(plan)
            selected = frame[[x_column, y_columns[0]]].copy()
            for column in selected.columns:
                selected[column] = pd.to_numeric(selected[column], errors="raise")
        except Exception as exc:
            raise EngineError("grapher_data_staging_failed", str(exc), engine="grapher") from exc
        return render_spec, selected

    @staticmethod
    def _readback_in_app(app: Any, artifact: Path) -> dict[str, Any]:
        document = None
        try:
            document = call(get(app, "Documents"), "Open", str(artifact))
            shapes = get(document, "Shapes")
            plots: list[dict[str, Any]] = []
            axes_payload: dict[str, Any] = {}
            graph_count = 0
            for shape_index in range(1, int(get(shapes, "Count")) + 1):
                shape = call(shapes, "Item", shape_index)
                graph_plots = _optional_get(shape, "Plots")
                graph_axes = _optional_get(shape, "Axes")
                if graph_plots is None or graph_axes is None:
                    continue
                graph_count += 1
                for plot_index in range(1, int(get(graph_plots, "Count")) + 1):
                    plot = call(graph_plots, "Item", plot_index)
                    plots.append(
                        {
                            "type": "xy_scatter"
                            if int(_optional_get(plot, "symbolFreq") or 0) == 1
                            else "xy_line",
                            "x_column_index": int(get(plot, "xCol")),
                            "y_column_index": int(get(plot, "yCol")),
                            "symbol_frequency": int(_optional_get(plot, "symbolFreq") or 0),
                            "line_width": float(_optional_get(get(plot, "line"), "width") or 0.0),
                            "object_type": int(get(plot, "Type")),
                        }
                    )
                for axis_index, key in ((1, "x"), (2, "y")):
                    if int(get(graph_axes, "Count")) >= axis_index:
                        axis = call(graph_axes, "Item", axis_index)
                        title = get(axis, "title")
                        axes_payload[key] = {
                            "present": True,
                            "title": str(get(title, "text")),
                            "object_type": int(get(axis, "Type")),
                        }
            return {
                "engine": "grapher",
                "document": {"opened": True, "path": str(artifact)},
                "graph_count": graph_count,
                "plots": plots,
                "axes": axes_payload,
            }
        finally:
            if document is not None:
                call(document, "Close", False)
                document = None

    def readback(self, artifact: str | Path) -> dict[str, Any]:
        path = Path(artifact).resolve()
        require_file(path, "grapher_readback_failed")
        with _application(visible=False) as (app, _metadata):
            return self._readback_in_app(app, path)

    def render(
        self,
        plan: dict[str, Any],
        *,
        plan_file: str | Path,
        engine_home: str | Path | None = None,
        python_executable: str | Path | None = None,
        output_dir: str | Path | None = None,
        close_application: bool = False,
    ) -> RenderResult:
        del engine_home, python_executable, close_application
        import editaplot_core

        editaplot_core.validate_plan(plan)
        render_spec, frame = self._prepare(plan)
        data = render_spec["data"]
        x_column, y_column = data["x"], data["y"][0]
        axes_spec = render_spec["axes"]
        style = render_spec.get("style") or {}
        size = render_spec.get("size_inches") or {}
        source = Path(plan["source"]["path"]).resolve()
        requested = (
            Path(output_dir).expanduser().resolve()
            if output_dir
            else _default_output_dir(source)
        )
        target = _claim_output(requested)
        input_copy = target / f"input_copy{source.suffix.lower()}"
        shutil.copy2(source, input_copy)
        shutil.copy2(Path(plan_file).resolve(), target / "render-plan.json")
        staging = target / "grapher_staging.csv"
        frame.to_csv(staging, index=False, encoding="utf-8-sig", lineterminator="\n")
        grf, png, pdf = (target / f"result.{suffix}" for suffix in ("grf", "png", "pdf"))
        colors = style.get("colors") or ["#1F6F78"]
        document = graph = plot = None
        with _application(visible=True) as (app, application):
            try:
                document = call(get(app, "Documents"), "Add", 0)
                graph = call(get(document, "Shapes"), "AddLinePlotGraph", str(staging), 1, 2)
                put(graph, "width", float(size.get("width", 6.5)))
                put(graph, "height", float(size.get("height", 4.5)))
                plots = get(graph, "Plots")
                plot = call(plots, "Item", 1)
                put(plot, "xCol", 1)
                put(plot, "yCol", 2)
                put(plot, "symbolFreq", 1)
                line = get(plot, "line")
                put(line, "width", 0.0)
                color = _color_value(str(colors[0]))
                put(line, "foreColor", color)
                symbol = get(plot, "symbol")
                put(symbol, "size", max(0.06, float(style.get("marker_size_pt") or 7.0) / 72.0))
                put(get(symbol, "Fill"), "foreColor", color)
                axes = get(graph, "Axes")
                put(get(call(axes, "Item", 1), "title"), "text", axes_spec["x"]["title"])
                put(get(call(axes, "Item", 2), "title"), "text", axes_spec["y"]["title"])
                title = str(plan["figure_contract"].get("core_conclusion") or "EditaPlot")
                put(get(graph, "title"), "text", title)
                call(document, "SaveAs", str(grf))
                require_file(grf, "grapher_save_failed")
                call(document, "Export2", str(png), False, "Defaults=0", True, "png")
                call(document, "Export2", str(pdf), False, "Defaults=0, EmbedFonts=1", True, "pdfv")
                require_file(png, "grapher_export_failed")
                require_file(pdf, "grapher_export_failed")
            except EngineError:
                raise
            except Exception as exc:
                raise EngineError("grapher_render_failed", str(exc), engine=self.name) from exc
            finally:
                graph = plot = None
                if document is not None:
                    call(document, "Close", False)
                    document = None

        manifest = {
            "schema_version": "1.0",
            "engine": self.name,
            "engine_version": application["version"],
            "editable_format": "grf",
            "plan_hash": plan["plan_hash"],
            "source": {
                "path": str(source),
                "sha256": plan["source"]["sha256"],
                "copy": str(input_copy),
            },
            "staging": {
                "path": str(staging),
                "sha256": _sha256(staging),
                "columns": [x_column, y_column],
            },
            "expected": {
                "chart_type": "xy_scatter",
                "x_column": x_column,
                "y_column": y_column,
                "x_title": axes_spec["x"]["title"],
                "y_title": axes_spec["y"]["title"],
            },
        }
        _write_json(target / "manifest.json", manifest)
        report = self.verify(target)
        if report["status"] != "ok":
            raise EngineError(
                "grapher_verify_failed",
                "Grapher render artifacts failed verification.",
                engine=self.name,
                report=str(target / "grapher_verify_report.json"),
            )
        result = RenderResult(
            engine=self.name,
            status="ok",
            output_dir=target,
            editable_path=grf,
            exports={"png": png, "pdf": pdf},
            readback=report["readback"],
            metadata={
                "engine_version": application["version"],
                "editable_format": "grf",
                "manifest": str(target / "manifest.json"),
                "verify_report": str(target / "grapher_verify_report.json"),
            },
        )
        _write_json(target / "render-result.json", result.to_dict())
        return result

    def verify(self, output_dir: str | Path) -> dict[str, Any]:
        target = Path(output_dir).expanduser().resolve()
        manifest_path = target / "manifest.json"
        expected_files = {
            "editable": target / "result.grf",
            "png": target / "result.png",
            "pdf": target / "result.pdf",
            "manifest": manifest_path,
        }
        artifacts = {
            name: {
                "path": str(path),
                "exists": path.is_file(),
                "size_bytes": path.stat().st_size if path.is_file() else 0,
            }
            for name, path in expected_files.items()
        }
        files_ok = all(item["size_bytes"] > 0 for item in artifacts.values())
        signatures_ok = False
        readback: dict[str, Any] = {}
        bindings_ok = axes_ok = False
        error: dict[str, str] | None = None
        try:
            if not files_ok:
                raise EngineError(
                    "grapher_artifact_missing", "One or more Grapher artifacts are missing."
                )
            signatures_ok = (
                expected_files["editable"].read_bytes().startswith(b"Grapher")
                and expected_files["png"].read_bytes().startswith(b"\x89PNG")
                and expected_files["pdf"].read_bytes().startswith(b"%PDF")
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            readback = self.readback(expected_files["editable"])
            expected = manifest["expected"]
            plot = readback["plots"][0] if readback.get("plots") else {}
            plot["x_column"] = expected["x_column"]
            plot["y_column"] = expected["y_column"]
            bindings_ok = (
                plot.get("type") == "xy_scatter"
                and plot.get("x_column_index") == 1
                and plot.get("y_column_index") == 2
            )
            axes_ok = (
                readback.get("axes", {}).get("x", {}).get("title") == expected["x_title"]
                and readback.get("axes", {}).get("y", {}).get("title") == expected["y_title"]
            )
        except Exception as exc:
            error = {"code": getattr(exc, "code", "grapher_verify_failed"), "message": str(exc)}
        ok = files_ok and signatures_ok and bindings_ok and axes_ok and error is None
        report: dict[str, Any] = {
            "status": "ok" if ok else "failed",
            "engine": self.name,
            "editable_format": "grf",
            "output_directory": str(target),
            "artifacts": artifacts,
            "checks": {
                "files_nonempty": files_ok,
                "native_signatures": signatures_ok,
                "document_reopened": bool(readback.get("document", {}).get("opened")),
                "plot_binding": bindings_ok,
                "axes": axes_ok,
            },
            "readback": readback,
        }
        if error:
            report["error"] = error
        try:
            _write_json(target / "grapher_verify_report.json", report)
        except OSError:
            pass
        return report


__all__ = ["GrapherEngine"]
