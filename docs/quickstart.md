# EditaPlot v0.1 quickstart (Windows)

Use a physical Windows 10/11 x64 computer with OriginPro 2024 and/or Golden Software Grapher 27 installed. Run these commands in PowerShell from the repository root. Each render creates a native editable project and verifies it after reopening. The example inputs are never modified.

## Setup and diagnosis

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .\runtime pywin32
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py --version
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py doctor --engine grapher --live --human
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py doctor --engine origin --engine-home runtime --live --human
```

`doctor` without `--live` preserves the earlier static JSON report. `--live` starts one fresh automation instance and requests a safe shutdown; it does not draw a figure or close an already open user instance. If Origin reports `unknown_process_remaining`, its COM instance cannot be mapped to a proven PID, so EditaPlot leaves the process alone. Close stale automation windows manually if a later job cannot start.

## CSV → Grapher → edit

Choose a new output directory for each run. Inspect the generated `workflow-preview.json` before confirming: check the selected route, X/Y columns, error meanings, and `confirmation_gate.can_confirm_now`.

```powershell
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py workflow-preview docs\quickstart-data\multiseries.csv --engine grapher --template-id trend --output-dir runs\grapher-01 --engine-home runtime
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py workflow-render runs\grapher-01\workflow-preview.json --claim "Compare Control and Treatment" --confirm --human
```

The summary lists `result.grf`, PNG, PDF, verification, and `session.json`. Open the GRF in Grapher to continue manual editing. In a **new PowerShell process**, continue the same verified project:

```powershell
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py edit runs\grapher-01\session.json "把 Treatment 改成虚线" --human
```

The edit reopens the GRF, modifies Treatment's native line style, saves, reopens and verifies it. Control remains unchanged.

## XLSX → Origin → edit

The selected `Data` sheet is copied to a CSV **inside the run directory**. The original XLSX stays read only. The two error columns drive native symmetric Y error bars.

```powershell
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py workflow-preview docs\quickstart-data\error.xlsx --sheet Data --engine origin --template-id line_error --output-dir runs\origin-01 --engine-home runtime
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py workflow-render runs\origin-01\workflow-preview.json --claim "Compare two series with uncertainty" --confirm --human
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py edit runs\origin-01\session.json "把 Y 轴标题改成 Current (mA)" --human
```

Open the resulting `result.opju` in Origin. The run contains PNG, PDF and TIF exports. To check artifacts again, use `verify <run>\origin --engine origin` or `verify <run>\grapher --engine grapher`.

## Optional advanced example: correlation matrix

The fixture below is explicitly synthetic, including its supplied p-values.
It demonstrates layout and scientific mapping, not experimental findings.

```powershell
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py workflow-preview tests\fixtures\correlation_heatmap\demo_correlation.csv --engine grapher --template-id heatmap --correlation-spec-json tests\fixtures\correlation_heatmap\demo_spec.json --output-dir runs\correlation-01 --engine-home runtime
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py workflow-render runs\correlation-01\workflow-preview.json --claim "Synthetic correlation layout example; supplied synthetic p-values" --confirm --human
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
version remains 0.1.0. Origin applies Whole Page before saving without resizing
the physical page. See
[layout evidence and limitations](correlation-heatmap-phase17.md).

## Problems and records

Normal output can be machine readable JSON; `--human` gives short result paths. Put `--verbose` **before the command** to retain native exception details in the run's `runtime.log`, for example `editaplot.py --verbose workflow-render ...`. A failed or interrupted session is never marked verified. `session.json` stores its status and error code; an interrupted `rendering`/`editing` session returns `incomplete_session` on retry. Start a new output directory rather than overwriting a prior run.

Grapher does not support native explicit per-point weighted Linear Fit; EditaPlot returns `unsupported_fit_weighting` and does not substitute an unweighted fit. Origin supports it. The available Grapher route set is 7 of 41 public Origin routes; see [route coverage](route-coverage-phase13.md).
