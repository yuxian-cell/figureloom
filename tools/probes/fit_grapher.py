"""Independent Grapher native linear-fit probe; never called by production render."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from grapher_sciplot.fit import _native_statistics
from grapher_sciplot.smoke import application, call, get, open_document


def parse_statistics(text: str) -> dict[str, float]:
    equation = re.search(r"Equation Y = ([+-]?[\d.]+) \* X ([+-]) ([\d.]+)", text)
    r_squared = re.search(r"Coefficient of determination, R-sq'd = ([\d.]+)", text)
    if not equation or not r_squared:
        raise ValueError("Grapher native statistics omitted linear parameters or R-squared")
    return {
        "slope": float(equation.group(1)),
        "intercept": float(equation.group(3)) * (1 if equation.group(2) == "+" else -1),
        "r_squared": float(r_squared.group(1)),
    }


def run(directory: Path) -> dict:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    csv = directory / "fit.csv"
    grf = directory / "fit_grapher.grf"
    csv.write_text("X,Y\n1,2.1\n2,4.0\n3,6.2\n4,8.1\n5,9.9\n", encoding="ascii")
    report: dict = {"status": "failed", "engine": "grapher", "artifacts": {"csv": str(csv), "grf": str(grf)}}
    app = doc = reopened = graph = plot = fit = None
    session = application(visible=True)
    entered = False
    try:
        app, report["application"] = session.__enter__()
        entered = True
        doc = call(get(app, "Documents"), "Add", 0)
        graph = call(get(doc, "Shapes"), "AddLinePlotGraph", str(csv), 1, 2)
        plot = call(get(graph, "Plots"), "Item", 1)
        fit = call(plot, "AddFit", 0)  # grfLinearFit, confirmed in installed Type Library
        report["created"] = {
            "fit_type": get(fit, "fitType"),
            "equation": str(get(fit, "Equation")),
            "fit_count": get(get(plot, "Fits"), "Count"),
            "x_column": get(plot, "xCol"),
            "y_column": get(plot, "yCol"),
            "min_x": get(fit, "MinX"),
            "max_x": get(fit, "MaxX"),
            "use_curve_limits": get(fit, "UseCurveLimits"),
        }
        call(doc, "SaveAs", str(grf))
        if not grf.is_file() or not grf.stat().st_size:
            raise RuntimeError("GRF save did not create a nonempty file")
        fit = plot = graph = None
        call(doc, "Close", False)
        doc = None
        reopened = open_document(app, grf)
        graph = call(get(reopened, "Shapes"), "Item", 1)
        plot = call(get(graph, "Plots"), "Item", 1)
        fit = call(get(plot, "Fits"), "Item", 1)
        report["native_statistics"] = _native_statistics(reopened, fit)
        report["result"] = parse_statistics(report["native_statistics"])
        report["readback"] = {
            "fit_type": get(fit, "fitType"),
            "equation": str(get(fit, "Equation")),
            "fit_count": get(get(plot, "Fits"), "Count"),
            "x_column": get(plot, "xCol"),
            "y_column": get(plot, "yCol"),
            "min_x": get(fit, "MinX"),
            "max_x": get(fit, "MaxX"),
            "use_curve_limits": get(fit, "UseCurveLimits"),
            "plot_count": get(get(graph, "Plots"), "Count"),
        }
        report["readback"]["fit_name"] = str(get(fit, "Name"))
        report["status"] = "ok"
    except Exception as exc:
        report["error"] = {
            "code": "fit_probe_failed",
            "stage": "grapher",
            "type": type(exc).__name__,
            "message": str(exc),
        }
    finally:
        fit = plot = graph = None
        for item in (reopened, doc):
            if item is not None:
                try:
                    call(item, "Close", False)
                except Exception as exc:
                    report["document_close_error"] = {"type": type(exc).__name__, "message": str(exc)}
        reopened = doc = None
        report["teardown_error"] = None
        if entered:
            try:
                session.__exit__(None, None, None)
            except Exception as exc:
                report["teardown_error"] = str(exc)
                report["status"] = "failed"
        app = None
        (directory / "fit_grapher.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return report


if __name__ == "__main__":
    result = run(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "ok" else 1)
