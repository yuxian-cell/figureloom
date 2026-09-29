# FigureLoom v0.2.0 quickstart (Windows)

Use a physical Windows 10/11 x64 computer with OriginPro 2024 and/or Golden Software Grapher 27 installed. Run these commands in PowerShell from the repository root. Each render creates a native editable project and verifies it after reopening. The example inputs are never modified.

## Setup and diagnosis

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements-runtime.lock -e .\runtime
.\.venv\Scripts\python.exe skill\figureloom\scripts\figureloom.py --version
.\.venv\Scripts\python.exe skill\figureloom\scripts\figureloom.py doctor --engine grapher --live --human
.\.venv\Scripts\python.exe skill\figureloom\scripts\figureloom.py doctor --engine origin --engine-home runtime --live --human
```

`doctor` without `--live` preserves the earlier static JSON report. `--live` starts one fresh automation instance and requests a safe shutdown; it does not draw a figure or close an already open user instance. If Origin reports `unknown_process_remaining`, its COM instance cannot be mapped to a proven PID, so FigureLoom leaves the process alone. Close stale automation windows manually if a later job cannot start.

## CSV → Grapher → edit

Choose a new output directory for each run. Inspect the generated `workflow-preview.json` before confirming: check the selected route, X/Y columns, error meanings, and `confirmation_gate.can_confirm_now`.

```powershell
.\.venv\Scripts\python.exe skill\figureloom\scripts\figureloom.py workflow-preview docs\quickstart-data\multiseries.csv --engine grapher --template-id trend --output-dir runs\grapher-01 --engine-home runtime
.\.venv\Scripts\python.exe skill\figureloom\scripts\figureloom.py workflow-render runs\grapher-01\workflow-preview.json --claim "Compare Control and Treatment" --confirm --human
```

The summary lists `result.grf`, PNG, PDF, verification, and `session.json`. Open the GRF in Grapher to continue manual editing. In a **new PowerShell process**, continue the same verified project:

```powershell
.\.venv\Scripts\python.exe skill\figureloom\scripts\figureloom.py edit runs\grapher-01\session.json "把 Treatment 改成虚线" --human
```

The edit reopens the GRF, modifies Treatment's native line style, saves, reopens and verifies it. Control remains unchanged.

## XLSX → Origin → edit

The selected `Data` sheet is copied to a CSV **inside the run directory**. The original XLSX stays read only. The two error columns drive native symmetric Y error bars.

```powershell
.\.venv\Scripts\python.exe skill\figureloom\scripts\figureloom.py workflow-preview docs\quickstart-data\error.xlsx --sheet Data --engine origin --template-id line_error --output-dir runs\origin-01 --engine-home runtime
.\.venv\Scripts\python.exe skill\figureloom\scripts\figureloom.py workflow-render runs\origin-01\workflow-preview.json --claim "Compare two series with uncertainty" --confirm --human
.\.venv\Scripts\python.exe skill\figureloom\scripts\figureloom.py edit runs\origin-01\session.json "把 Y 轴标题改成 Current (mA)" --human
```

Open the resulting `result.opju` in Origin. The run contains PNG, PDF and TIF exports. To check artifacts again, use `verify <run>\origin --engine origin` or `verify <run>\grapher --engine grapher`.

## Optional advanced example: correlation matrix

The fixture below is explicitly synthetic, including its supplied p-values.
It demonstrates layout and scientific mapping, not experimental findings.

```powershell
.\.venv\Scripts\python.exe skill\figureloom\scripts\figureloom.py workflow-preview tests\fixtures\correlation_heatmap\demo_correlation.csv --engine grapher --template-id heatmap --correlation-spec-json tests\fixtures\correlation_heatmap\demo_spec.json --output-dir runs\correlation-01 --engine-home runtime
.\.venv\Scripts\python.exe skill\figureloom\scripts\figureloom.py workflow-render runs\correlation-01\workflow-preview.json --claim "Synthetic correlation layout example; supplied synthetic p-values" --confirm --human
```

Use `--engine origin` and a fresh directory for the equivalent native Matrix
Heatmap. Origin exports OPJU/PNG/PDF/TIF; Grapher exports GRF/PNG/PDF and uses a
native 21-interval class legend. Keep `correlation_cells.csv` beside the GRF as
its editable native worksheet backing data. This correlation submode does not
enable arbitrary generic Grapher heatmaps. Recommended size is at most 10×10;
the tested hard limit is 20×20. Heatmap AI EditPlan operations are not supported.

Phase 17 adds deterministic physical layout planning for this correlation submode:
long labels and value/star text enlarge cells, margins and the native page, rather
than shrinking text. Full labels are retained; X-label rotation is selected from
45/60/90 degrees. Annotation sizes are Origin 11 pt and Grapher 10 pt. Matrices
above 10 labels still receive a density warning. Inspect the native project at
the intended physical output size before publication. Phase 17 real-data GUI
acceptance passed, including the final Origin Whole Page reopen spot-check;
version is now 0.2.0. Origin applies Whole Page before saving without resizing
the physical page. See
[layout evidence and limitations](correlation-heatmap-phase17.md).

### Supplied matrix, supplied p-values, or raw Pearson (API)

The current CLI accepts a frozen `--correlation-spec-json`; it does not directly
calculate raw Pearson or load a separate p-value CSV. This Python API example
prepares the explicit spec, then uses the same preview/confirmation/native
render workflow. Run from the repository root with the installed runtime.
Choose a new output directory for every run; use `engine="origin"` for OPJU.

```python
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, "skill/figureloom/scripts")
from figureloom_engine.correlation_heatmap import CorrelationHeatmapSpec
from figureloom_engine.workflow import preview, render_confirmed

matrix_file = Path("tests/fixtures/correlation_heatmap/concrete_correlation.csv")
matrix = pd.read_csv(matrix_file, index_col=0, float_precision="round_trip")
assert list(matrix.index) == list(matrix.columns)

def draw(source, matrix, pvalues, output):
    spec = CorrelationHeatmapSpec(
        list(matrix.columns), matrix.to_numpy().tolist(),
        None if pvalues is None else pvalues.to_numpy().tolist(),
        significance_enabled=pvalues is not None, title="Concrete correlation",
    )
    preview(source, output, engine_name="grapher", template_id="heatmap",
            correlation_heatmap_spec=spec.to_dict(), engine_home=Path("runtime"))
    # Review workflow-preview.json and its confirmation gate before this call.
    return render_confirmed(Path(output) / "workflow-preview.json", confirmed=True,
                            claim="Explicit Concrete correlation matrix and p-value semantics")

# A: matrix only — no stars or inferred p-values.
draw(matrix_file, matrix, None, "runs/correlation-matrix-01")

# B: explicit supplied p-values, in exactly the same label order.
pvalues = pd.read_csv("tests/fixtures/correlation_heatmap/concrete_pvalues.csv",
                     index_col=0, float_precision="round_trip")
assert list(pvalues.index) == list(matrix.index)
assert list(pvalues.columns) == list(matrix.columns)
draw(matrix_file, matrix, pvalues, "runs/correlation-pvalues-01")
```

For **C: raw observations**, additionally provide SciPy (the validated analysis
version is 1.14.1). This is explicit data preparation; the native backend renders
the derived matrix. The complete Concrete fixture uses all 1030 finite numeric
rows. This example rejects invalid data instead of silently dropping rows.
Set `FIGURELOOM_CONCRETE_RAW` to your local raw CSV path and retain the derived
files/provenance.

```python
import hashlib
import json
import os
import numpy as np
from scipy.stats import pearsonr

raw_file = Path(os.environ["FIGURELOOM_CONCRETE_RAW"])
raw = pd.read_csv(raw_file)
values = raw.to_numpy(dtype=float)
assert len(values) >= 3 and np.isfinite(values).all()
r, p = np.eye(len(raw.columns)), np.zeros((len(raw.columns), len(raw.columns)))
for i in range(len(raw.columns)):
    for j in range(i):
        result = pearsonr(values[:, i], values[:, j], alternative="two-sided")
        r[i, j] = r[j, i] = result.statistic
        p[i, j] = p[j, i] = result.pvalue
prepared = Path("runs/pearson-input-01")
prepared.mkdir(parents=True, exist_ok=False)
matrix = pd.DataFrame(r, index=raw.columns, columns=raw.columns)
pvalues = pd.DataFrame(p, index=raw.columns, columns=raw.columns)
matrix_file = prepared / "correlation.csv"
matrix.to_csv(matrix_file, index_label="Variable")
pvalues.to_csv(prepared / "pvalues.csv", index_label="Variable")
(prepared / "provenance.json").write_text(json.dumps({
    "raw_source": str(raw_file), "sha256": hashlib.sha256(raw_file.read_bytes()).hexdigest(),
    "n_points": len(raw), "excluded_rows": 0, "method": "Pearson",
    "alternative": "two-sided", "multiple_comparison_correction": "none",
}), encoding="utf-8")
draw(matrix_file, matrix, pvalues, "runs/correlation-raw-01")
```

P-values are explicit inputs in A/B and explicitly computed in C; no correction
is applied. Keep Grapher's GRF and `correlation_cells.csv` together. See
[v0.2.0 release notes](release-v0.2.md) for backend differences and limitations.

## Problems and records

Normal output can be machine readable JSON; `--human` gives short result paths. Put `--verbose` **before the command** to retain native exception details in the run's `runtime.log`, for example `figureloom.py --verbose workflow-render ...`. A failed or interrupted session is never marked verified. `session.json` stores its status and error code; an interrupted `rendering`/`editing` session returns `incomplete_session` on retry. Start a new output directory rather than overwriting a prior run.

Grapher does not support native explicit per-point weighted Linear Fit; FigureLoom returns `unsupported_fit_weighting` and does not substitute an unweighted fit. Origin supports it. The available Grapher route set is 7 of 41 public Origin routes; see [route coverage](route-coverage-phase13.md).
