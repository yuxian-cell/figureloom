# EditaPlot v0.1 release notes

EditaPlot v0.1 is a Windows Python/CLI release for inspect → recommend → understand → explicit confirmation → RenderPlan → native Origin or Grapher render → save/reopen/readback/verify → session resume → limited native edit. Start with [Quickstart](quickstart.md).

## What works

- CSV and XLSX input, including explicit XLSX sheet selection, without changing the source file.
- OriginPro 2024 produces editable OPJU plus PNG, PDF and TIF. Existing 41 Origin public routes retain their Phase 14 behavior.
- Grapher 27 produces editable GRF plus PNG and PDF for seven verified public routes: `scatter`, `trend`, `line_error`, `bar`, `cv`, `lsv`, `xas`. Native XY, symmetric Y error, Bar and supported Fit objects survive save/reopen.
- Verified sessions persist in `session.json` and can be edited from a later CLI process. v0.1 edits are X/Y axis titles and Grapher named-series solid/dashed line style.
- `doctor --live --human` performs a basic isolated native activation/shutdown check. `--verbose` retains native exception traces in a per-run `runtime.log`.

## Known limitations

- Grapher has no verified native explicit per-point weighted Linear Fit; requests fail with `unsupported_fit_weighting`. Origin supports direct weights.
- Grapher automation uses one isolated COM instance per job. Many jobs in one long-lived Python process may encounter COM access conflicts.
- The installed Origin external COM API does not provide a verified PID/HWND ownership identity. Exit and Python-reference release are attempted; an immediate doctor check may report `unknown_process_remaining`. Native Fit teardown can still print `0x800706be`, and unknown residual processes have been observed after the 13-case suite. Subsequent doctor/render/edit jobs recovered successfully. EditaPlot never kills an unproven Origin process.
- Grapher covers 7 of 41 public Origin routes. The other routes are not silently rendered as approximations. See [route coverage](route-coverage-phase13.md).
- Origin automatic Fit statistics boxes can be crowded for multiple Fits.
- EditPlan is intentionally limited; it does not edit Fit range or arbitrary plot properties. There is no desktop shell or installer in this release.

## Use

```powershell
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py --version
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py doctor --engine grapher --live --human
.\.venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py workflow-preview docs\quickstart-data\multiseries.csv --engine grapher --template-id trend --output-dir runs\grapher-01 --engine-home runtime
```

Review and confirm the generated `workflow-preview.json`, then follow the render/edit commands in [Quickstart](quickstart.md). Successful output names the native project, exports, verification status and session path.
