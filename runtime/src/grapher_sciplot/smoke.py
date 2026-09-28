"""Exercise a real Grapher document, export, reopen, and object readback."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from figureloom_engine.models import EngineError

PROGID = "Grapher.Application"


class SmokeFailure(EngineError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, engine="grapher")


def discover() -> dict[str, str]:
    if platform.system() != "Windows":
        raise SmokeFailure("unsupported_platform", "Grapher automation requires Windows.")
    import winreg

    installed = any(
        (Path(root) / "Golden Software" / "Grapher" / "Grapher.exe").is_file()
        for root in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""))
        if root
    )
    try:
        clsid = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, PROGID + r"\CLSID")
        server = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32")
    except OSError as exc:
        code = "grapher_com_class_not_registered" if installed else "grapher_not_installed"
        raise SmokeFailure(code, "Grapher COM registration was not found.") from exc
    match = re.match(r'\s*"?(.+?\.exe)"?(?:\s|$)', server, re.IGNORECASE)
    exe = match.group(1) if match else ""
    if not Path(exe).is_file():
        raise SmokeFailure("grapher_not_installed", "Registered Grapher executable is missing.")
    return {"progid": PROGID, "clsid": clsid, "executable": exe}


def require_file(path: Path, code: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise SmokeFailure(code, f"Grapher did not create a nonempty {path.name}.")


def grapher_pids() -> set[int]:
    result = subprocess.run(  # noqa: S603 - fixed Windows system command
        [
            str(Path(os.environ["SystemRoot"]) / "System32" / "tasklist.exe"),
            "/FI",
            "IMAGENAME eq Grapher.exe",
            "/FO",
            "CSV",
            "/NH",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        int(row[1]) for row in csv.reader(result.stdout.splitlines())
        if len(row) > 1 and row[0].casefold() == "grapher.exe"
    }


def quit_owned_application(app: Any, pid: int | None = None) -> str | None:
    """Request COM shutdown; process exit is checked after the Python job exits."""

    del pid  # A process-list difference is diagnostic, not ownership proof.
    try:
        call(app, "Quit")
    except Exception as exc:
        return f"application_quit: {exc}"
    return None


def _dispatch(obj: Any) -> Any:
    return getattr(obj, "_oleobj_", obj)


def call(obj: Any, name: str, *args: Any) -> Any:
    import pythoncom

    # The installed Grapher 27 type library has stale DISPIDs; resolve live names.
    dispatch = _dispatch(obj)
    return dispatch.Invoke(dispatch.GetIDsOfNames(name), 0, pythoncom.DISPATCH_METHOD, True, *args)


def get(obj: Any, name: str) -> Any:
    import pythoncom

    dispatch = _dispatch(obj)
    return dispatch.Invoke(dispatch.GetIDsOfNames(name), 0, pythoncom.DISPATCH_PROPERTYGET, True)


def put(obj: Any, name: str, value: Any) -> None:
    import pythoncom

    dispatch = _dispatch(obj)
    dispatch.Invoke(dispatch.GetIDsOfNames(name), 0, pythoncom.DISPATCH_PROPERTYPUT, False, value)


def run_smoke(output_dir: Path | None = None, *, visible: bool = True) -> dict[str, Any]:
    report: dict[str, Any] = {"status": "failed", "engine": "grapher"}
    app = doc = reopened = None
    owned_pid: int | None = None
    pythoncom = None
    try:
        registration = discover()
        report["application"] = registration
        try:
            import pythoncom as com
            from win32com.client import DispatchEx
        except ImportError as exc:
            raise SmokeFailure(
                "grapher_com_activation_failed", "pywin32 is required for Grapher COM automation."
            ) from exc

        pythoncom = com
        base = Path(output_dir).expanduser().resolve() if output_dir else None
        if base:
            base.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="grapher-smoke-", dir=base))
        grf, png, pdf = (work / f"smoke.{suffix}" for suffix in ("grf", "png", "pdf"))
        data = work / "smoke.csv"
        data.write_text("X,Y\n1,1\n2,4\n3,9\n4,16\n5,25\n", encoding="ascii")
        report["artifacts"] = {"grf": str(grf), "png": str(png), "pdf": str(pdf), "data": str(data)}
        report["report_path"] = str(work / "smoke-report.json")

        before_pids = grapher_pids()
        com.CoInitialize()
        try:
            app = DispatchEx(PROGID)
            new_pids = grapher_pids() - before_pids
            if len(new_pids) != 1:
                raise SmokeFailure(
                    "grapher_com_activation_failed", "COM did not create one isolated Grapher process."
                )
            owned_pid = new_pids.pop()
            put(app, "Visible", visible)
            report["application"].update(
                version=str(get(app, "Version")),
                visible=bool(get(app, "Visible")),
                pid=owned_pid,
            )
        except SmokeFailure:
            raise
        except Exception as exc:
            raise SmokeFailure("grapher_com_activation_failed", str(exc)) from exc

        try:
            doc = call(get(app, "Documents"), "Add", 0)  # grfPlotDoc
        except Exception as exc:
            raise SmokeFailure("grapher_document_create_failed", str(exc)) from exc
        try:
            graph = call(get(doc, "Shapes"), "AddLinePlotGraph", str(data), 1, 2)
            graph_type = get(graph, "Type")
            plot = call(get(graph, "Plots"), "Item", 1)
            put(plot, "xCol", 1)
            put(plot, "yCol", 2)
            axes = get(graph, "Axes")
            put(get(call(axes, "Item", 1), "title"), "text", "X")
            put(get(call(axes, "Item", 2), "title"), "text", "Y")
            put(get(graph, "title"), "text", "Grapher smoke")
        except Exception as exc:
            raise SmokeFailure("grapher_plot_create_failed", str(exc)) from exc
        finally:
            graph = plot = None

        try:
            call(doc, "SaveAs", str(grf))
            require_file(grf, "grapher_save_failed")
        except SmokeFailure:
            raise
        except Exception as exc:
            raise SmokeFailure("grapher_save_failed", str(exc)) from exc
        try:
            call(doc, "Export2", str(png), False, "Defaults=0", True, "png")
            call(doc, "Export2", str(pdf), False, "Defaults=0, EmbedFonts=1", True, "pdfv")
            require_file(png, "grapher_export_failed")
            require_file(pdf, "grapher_export_failed")
        except SmokeFailure:
            raise
        except Exception as exc:
            raise SmokeFailure("grapher_export_failed", str(exc)) from exc

        try:
            call(doc, "Close", False)
            doc = None
            reopened = call(get(app, "Documents"), "Open", str(grf))
            graph_count = 0
            plot_count = axis_count = 0
            columns: list[dict[str, int]] = []
            shapes = get(reopened, "Shapes")
            for index in range(1, get(shapes, "Count") + 1):
                shape = call(shapes, "Item", index)
                if get(shape, "Type") != graph_type:
                    continue
                plots, axes = get(shape, "Plots"), get(shape, "Axes")
                graph_count += 1
                plot_count += get(plots, "Count")
                axis_count += get(axes, "Count")
                for plot_index in range(1, get(plots, "Count") + 1):
                    item = call(plots, "Item", plot_index)
                    columns.append({"x": int(get(item, "xCol")), "y": int(get(item, "yCol"))})
            report["readback"] = {
                "document_opened": True,
                "graph_count": graph_count,
                "plot_count": plot_count,
                "axis_count": axis_count,
                "graph_object_type": graph_type,
                "columns": columns,
            }
            if graph_count < 1 or plot_count < 1 or axis_count < 2 or {"x": 1, "y": 2} not in columns:
                raise SmokeFailure(
                    "grapher_readback_failed", "Reopened GRF lacks the native XY graph objects."
                )
        except SmokeFailure:
            raise
        except Exception as exc:
            raise SmokeFailure("grapher_readback_failed", str(exc)) from exc
        report["status"] = "ok"
    except SmokeFailure as exc:
        report["error"] = {"code": exc.code, "message": str(exc)}
    except Exception as exc:
        report["error"] = {"code": "grapher_smoke_failed", "message": str(exc)}
    finally:
        document_errors: list[str] = []
        for document in (reopened, doc):
            if document is not None:
                try:
                    call(document, "Close", False)
                except Exception as exc:
                    document_errors.append(f"document_close: {exc}")
        cleanup_errors: list[str] = []
        if app is not None:
            cleanup_error = quit_owned_application(app, owned_pid)
            if cleanup_error:
                cleanup_errors.extend((*document_errors, cleanup_error))
        else:
            cleanup_errors.extend(document_errors)
        reopened = doc = app = None
        if pythoncom is not None:
            pythoncom.CoUninitialize()
        if cleanup_errors:
            if report["status"] == "failed" and "error" in report:
                report["cleanup_warning"] = "; ".join(cleanup_errors)
            else:
                report["status"] = "failed"
                report["error"] = {"code": "grapher_cleanup_failed", "message": "; ".join(cleanup_errors)}
        if "report_path" in report:
            try:
                Path(report["report_path"]).write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except OSError as exc:
                report["status"] = "failed"
                report["error"] = {"code": "grapher_report_write_failed", "message": str(exc)}
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the native Grapher automation smoke test")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--hidden", action="store_true")
    args = parser.parse_args(argv)
    report = run_smoke(args.output_dir, visible=not args.hidden)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
