"""Independent Origin native linear-fit probe; never called by production render."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from origin_sciplot.origin_backend.session import OriginSession


def run(directory: Path) -> dict:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    csv = directory / "fit.csv"
    opju = directory / "fit_origin.opju"
    csv.write_text("X,Y\n1,2.1\n2,4.0\n3,6.2\n4,8.1\n5,9.9\n", encoding="ascii")
    report: dict = {"status": "failed", "engine": "origin", "artifacts": {"csv": str(csv), "opju": str(opju)}}
    try:
        with OriginSession(keep_open=False) as session:
            op = session.op
            op.set_show(True)
            report["application"] = session.environment.to_dict()
            book = op.new_book(lname="Native Linear Fit Probe")
            sheet = book[0]
            sheet.from_list(0, [1, 2, 3, 4, 5], "X", axis="X")
            sheet.from_list(1, [2.1, 4.0, 6.2, 8.1, 9.9], "Y", axis="Y")
            graph = op.new_graph(lname="Scatter with Native Linear Fit")
            layer = graph[0]
            layer.add_plot(sheet, 1, 0, type="s")
            layer.rescale()
            fit = op.LinearFit()
            fit.set_data(sheet, 0, 1)
            report_sheet, curve_sheet = fit.report()
            report["created"] = {"report_sheet": report_sheet, "curve_sheet": curve_sheet}
            if curve_sheet:
                fit_curve = op.find_sheet("w", curve_sheet)
                if fit_curve is not None:
                    layer.add_plot(fit_curve, 1, 0, type="l")
                    layer.rescale()
            graph_name, source_ref = graph.name, f"[{book.name}]{sheet.name}!"
            op.save(str(opju))
            if not opju.is_file() or not opju.stat().st_size:
                raise RuntimeError("OPJU save did not create a nonempty file")
            op.new(asksave=False)
            op.open(str(opju), asksave=False)
            reopened_report = op.find_sheet("w", report_sheet)
            reopened_curve = op.find_sheet("w", curve_sheet)
            reopened_graph = op.find_graph(graph_name)
            reopened_source = op.find_sheet("w", source_ref)
            columns = (
                [reopened_report.to_list(i) for i in range(reopened_report.shape[1])]
                if reopened_report
                else []
            )
            if not columns or len(columns[8]) < 2 or len(columns[12]) < 5:
                raise RuntimeError("Origin native fit report lacks parameter or R-squared cells")
            report["readback"] = {
                "report_sheet_exists": reopened_report is not None,
                "curve_sheet_exists": reopened_curve is not None,
                "graph_exists": reopened_graph is not None,
                "source_sheet_exists": reopened_source is not None,
                "source_x": reopened_source.to_list(0) if reopened_source else None,
                "source_y": reopened_source.to_list(1) if reopened_source else None,
                "report_shape": reopened_report.shape,
                "model": columns[2][3],
                "source_x_binding": columns[3][0],
                "source_y_binding": columns[4][0],
                "fit_range": columns[5][0],
                "weighting": columns[2][5],
                "curve_x": reopened_curve.to_list(0)[:7] if reopened_curve else None,
                "curve_y": reopened_curve.to_list(1)[:7] if reopened_curve else None,
            }
            report["result"] = {
                "intercept": float(columns[8][0]),
                "slope": float(columns[8][1]),
                "r_squared": float(columns[12][4]),
            }
            report["status"] = (
                "ok"
                if all(
                    report["readback"][k]
                    for k in ("report_sheet_exists", "curve_sheet_exists", "graph_exists")
                )
                else "failed"
            )
    except Exception as exc:
        report["error"] = {
            "code": "fit_probe_failed",
            "stage": "origin",
            "type": type(exc).__name__,
            "message": str(exc),
        }
    (directory / "fit_origin.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    result = run(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "ok" else 1)
