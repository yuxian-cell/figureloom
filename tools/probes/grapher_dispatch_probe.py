"""Read live Grapher Linear Fit IDispatch metadata from a saved GRF."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pythoncom
from grapher_sciplot.smoke import application, open_document

NAMES = (
    "Weight", "Weights", "WeightColumn", "Weighting", "Weighted", "Sigma",
    "Error", "ErrorColumn", "Variance", "Instrumental", "Uncertainty",
    "Regression", "Data", "Column", "SetWeight", "LoadWeights", "SaveWeights",
)


def call(obj: object, name: str, *args: object) -> object:
    dispatch = getattr(obj, "_oleobj_", obj)
    return dispatch.Invoke(dispatch.GetIDsOfNames(name), 0, pythoncom.DISPATCH_METHOD, True, *args)


def get(obj: object, name: str) -> object:
    dispatch = getattr(obj, "_oleobj_", obj)
    return dispatch.Invoke(dispatch.GetIDsOfNames(name), 0, pythoncom.DISPATCH_PROPERTYGET, True)


def put(obj: object, name: str, value: object) -> None:
    dispatch = getattr(obj, "_oleobj_", obj)
    dispatch.Invoke(dispatch.GetIDsOfNames(name), 0, pythoncom.DISPATCH_PROPERTYPUT, False, value)


def main(path: Path) -> None:
    with application(visible=False) as (app, _info):
        document = None
        try:
            document = open_document(app, path.resolve())
            shapes = get(document, "Shapes")
            fit = None
            source_plot = None
            for shape_index in range(1, int(get(shapes, "Count")) + 1):
                shape = call(shapes, "Item", shape_index)
                try:
                    plots = get(shape, "Plots")
                except pythoncom.com_error:
                    continue
                for plot_index in range(1, int(get(plots, "Count")) + 1):
                    plot = call(plots, "Item", plot_index)
                    fits = get(plot, "Fits")
                    if int(get(fits, "Count")):
                        fit = call(fits, "Item", 1)
                        source_plot = plot
                        break
                if fit is not None:
                    break
            if fit is None:
                raise RuntimeError("Saved GRF contains no Fit object")
            dispatch = getattr(fit, "_oleobj_", fit)
            try:
                info = dispatch.GetTypeInfo(0)
            except pythoncom.com_error:
                info = None
            candidates = {}
            for name in NAMES:
                try:
                    candidates[name] = dispatch.GetIDsOfNames(name)
                except pythoncom.com_error:
                    candidates[name] = None
            try:
                call(fit, "SetWeight", 1, 10.0)
                set_weight = "accepted"
            except pythoncom.com_error as exc:
                set_weight = f"rejected: {exc.excepinfo[2] if exc.excepinfo else exc}"
            weighted_average = call(source_plot, "AddFit", 9)  # grfWeightedAvgFit
            try:
                call(weighted_average, "SetWeight", 1, 10.0)
                weighted_average_set_weight = "accepted"
            except pythoncom.com_error as exc:
                weighted_average_set_weight = f"rejected: {exc.excepinfo[2] if exc.excepinfo else exc}"
            print(json.dumps({
                "version": get(app, "Version"),
                "fit_type": get(fit, "fitType"),
                "runtime_typeinfo_available": info is not None,
                "interface": info.GetDocumentation(-1)[0] if info is not None else None,
                "candidate_dispids": candidates,
                "linear_set_weight_probe": set_weight,
                "weighted_average_fit_type": get(weighted_average, "fitType"),
                "weighted_average_set_weight_probe": weighted_average_set_weight,
            }, indent=2, default=str))
        finally:
            if document is not None:
                call(document, "Close", False)
            document = None


if __name__ == "__main__":
    main(Path(sys.argv[1]))
