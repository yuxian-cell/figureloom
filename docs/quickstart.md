# EditaPlot workflow quickstart

Run from the repository root with the project's Python environment.

```powershell
.\.test-venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py workflow-preview data.csv --engine grapher --template-id trend --output-dir my-run --engine-home runtime
```

Review `my-run/workflow-preview.json`: inspect the selected template, X/Y columns, error meanings and `confirmation_gate`. Correct the source or mapping if any column is uncertain. Then explicitly confirm and render:

```powershell
.\.test-venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py workflow-render my-run\workflow-preview.json --claim "Treatment exceeds Control" --confirm
```

The native project and exports are listed in `my-run/session.json`. Continue editing that **same project** in a later command:

```powershell
.\.test-venv\Scripts\python.exe skill\editaplot\scripts\editaplot.py edit my-run\session.json "把 Treatment 改成虚线"
```

For XLSX, add `--sheet Data` to `workflow-preview` and select `--engine origin`. Both engines support an axis-title edit such as `"把 Y 轴标题改成 Current (mA)"`. Grapher supports the named-series solid/dashed edit. The workflow never modifies the input CSV/XLSX. `--template-id` is an optional explicit override; the preview also presents compatible recommendations when it is omitted.
