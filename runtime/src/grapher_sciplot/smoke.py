"""Exercise a real Grapher document, export, reopen, and object readback."""

from __future__ import annotations

import argparse
import csv
import ctypes
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
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
    """Request COM shutdown for an application whose ownership was verified."""

    del pid  # A process-list difference is diagnostic, not ownership proof.
    try:
        call(app, "Quit")
    except Exception as exc:
        return f"application_quit: {exc}"
    return None


def _start_application(executable: str) -> subprocess.Popen:
    """Keep the child handle as ownership evidence; never infer it from a PID difference."""
    process = subprocess.Popen([executable, "/Automation"])  # noqa: S603 - registered local executable
    wait = ctypes.WinDLL("user32", use_last_error=True).WaitForInputIdle
    wait.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    wait.restype = ctypes.c_uint32
    if wait(int(process._handle), 10000) != 0:
        raise SmokeFailure("grapher_com_activation_failed", "Grapher startup did not become idle.")
    # Input-idle precedes COM server readiness on 27.1.296. Identity is still checked below.
    time.sleep(0.5)
    return process


@contextmanager
def application(*, visible: bool) -> Iterator[tuple[Any, dict[str, Any]]]:
    """Attach to a user's single-instance server, or launch and own a verified child."""
    try:
        import pythoncom
        from win32com.client import DispatchEx, GetActiveObject
    except ImportError as exc:
        raise SmokeFailure(
            "grapher_com_activation_failed", "pywin32 is required for Grapher COM automation."
        ) from exc
    registration = discover()
    app = process = None
    ownership = False
    pythoncom.CoInitialize()
    try:
        before = grapher_pids()
        if len(before) > 1:
            raise SmokeFailure(
                "grapher_ownership_unverified",
                "Multiple Grapher processes are open; no activation attempted.",
            )
        try:
            app = GetActiveObject(PROGID)
        except pythoncom.com_error as exc:
            if exc.hresult != -2147221021:  # MK_E_UNAVAILABLE: no object in the ROT
                raise SmokeFailure("grapher_com_activation_failed", str(exc)) from exc
        if app is None and not before:
            process = _start_application(registration["executable"])
        if app is None:
            # 27.1.296 does not register its application in the ROT. Activation attaches
            # to a ready desktop instance; startup can temporarily reject activation.
            for attempt in range(40):
                try:
                    app = DispatchEx(PROGID)
                    break
                except pythoncom.com_error as exc:
                    if attempt == 39:
                        raise SmokeFailure("grapher_com_activation_failed", str(exc)) from exc
                    time.sleep(0.25)
                except Exception as exc:
                    raise SmokeFailure("grapher_com_activation_failed", str(exc)) from exc
        current = grapher_pids()
        if process is not None:
            if (
                process.poll() is not None or current != {process.pid}
                or bool(get(app, "Visible")) or int(get(get(app, "Documents"), "Count")) != 0
                or Path(str(get(app, "FullName"))).resolve() != Path(registration["executable"]).resolve()
            ):
                raise SmokeFailure(
                    "grapher_ownership_unverified", "Grapher ownership is ambiguous; no Quit was requested."
                )
            ownership = True
            put(app, "Visible", visible)
        elif len(current) != 1 or (before and current != before):
            raise SmokeFailure(
                "grapher_ownership_unverified", "The existing Grapher instance could not be identified."
            )
        yield app, {
            **registration, "version": str(get(app, "Version")),
            "visible": bool(get(app, "Visible")), "pid": next(iter(current)),
            "ownership": ownership, "connection_mode": "own" if ownership else "attach",
        }
    except EngineError:
        raise
    except Exception as exc:
        raise SmokeFailure("grapher_native_operation_failed", "Grapher native automation failed.") from exc
    finally:
        primary_error = sys.exc_info()[1]
        cleanup_error = None
        shutdown_requested = False
        if app is not None and ownership:
            try:
                if process.poll() is not None or grapher_pids() != {process.pid}:
                    cleanup_error = "Grapher identity changed; no Quit was requested."
                elif int(get(get(app, "Documents"), "Count")) != 0:
                    cleanup_error = "Grapher has open documents; no Quit was requested."
                else:
                    cleanup_error = quit_owned_application(app, process.pid)
                    shutdown_requested = cleanup_error is None
            except Exception as exc:
                cleanup_error = f"Grapher shutdown could not be verified: {exc}"
        app = None
        pythoncom.CoUninitialize()
        if shutdown_requested:
            # Quit is asynchronous. Finish this lease before another activation can
            # mistake its exiting child for a preexisting user application.
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cleanup_error = "Owned Grapher did not exit after Quit; no process was killed."
        if cleanup_error:
            if primary_error is not None:
                primary_error.add_note(f"Grapher cleanup warning: {cleanup_error}")
            else:
                raise SmokeFailure("grapher_cleanup_failed", cleanup_error)


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


def open_document(app: Any, path: Path) -> Any:
    """Never acquire and later close a document already open in the user's window."""
    documents = get(app, "Documents")
    for index in range(1, int(get(documents, "Count")) + 1):
        document = call(documents, "Item", index)
        fullname = str(get(document, "FullName"))
        if fullname and Path(fullname).resolve() == path.resolve():
            raise SmokeFailure(
                "grapher_document_in_use", "Close this GRF in Grapher before editing or verifying it."
            )
    return call(documents, "Open", str(path))


def _smoke_document(app: Any, report: dict[str, Any], grf: Path, png: Path, pdf: Path, data: Path) -> None:
    doc = reopened = None
    try:
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
            reopened = open_document(app, grf)
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
    finally:
        errors = []
        for document in (reopened, doc):
            if document is not None:
                try:
                    call(document, "Close", False)
                except Exception as exc:
                    errors.append(f"document_close: {exc}")
        if errors:
            primary = sys.exc_info()[1]
            if primary is not None:
                primary.add_note("Grapher cleanup warning: " + "; ".join(errors))
            else:
                raise SmokeFailure("grapher_cleanup_failed", "; ".join(errors))


def run_smoke(output_dir: Path | None = None, *, visible: bool = True) -> dict[str, Any]:
    report: dict[str, Any] = {"status": "failed", "engine": "grapher"}
    try:
        report["application"] = discover()
        base = Path(output_dir).expanduser().resolve() if output_dir else None
        if base:
            base.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="grapher-smoke-", dir=base))
        grf, png, pdf = (work / f"smoke.{suffix}" for suffix in ("grf", "png", "pdf"))
        data = work / "smoke.csv"
        data.write_text("X,Y\n1,1\n2,4\n3,9\n4,16\n5,25\n", encoding="ascii")
        report["artifacts"] = {"grf": str(grf), "png": str(png), "pdf": str(pdf), "data": str(data)}
        report["report_path"] = str(work / "smoke-report.json")

        with application(visible=visible) as (app, info):
            report["application"] = info
            try:
                _smoke_document(app, report, grf, png, pdf, data)
            finally:
                app = None
    except EngineError as exc:
        report["status"] = "failed"
        report["error"] = {"code": exc.code, "message": str(exc)}
        if getattr(exc, "__notes__", None):
            report["cleanup_warning"] = "; ".join(exc.__notes__)
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = {"code": "grapher_smoke_failed", "message": str(exc)}
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
