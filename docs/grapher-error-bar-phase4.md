# Phase 4: symmetric Y error bars

## Origin GUI prerequisite (passed)

The retained standard project is `.phase3-e2e/origin_regression/result.opju`. Its earlier
programmatic Origin readback and export verification passed. On 2026-09-25 the user opened the
OPJU in OriginPro 2024 and supplied a screenshot. It shows the native `Graph1 - SCATTER Figure`
window, five points at the expected X/Y positions, X and Y labels, readable axes, and one
checked Y plot in Origin's Object Manager. The plot appears editable and the source workbooks
remain in the project. A single-series scatter needs no legend. There is no visible style
regression. This satisfies the phase-3 GUI visual gate for the standard fixture; no edits were
made to the Origin renderer.

## Existing error data flow

`prepare_scientific` recognizes error role columns for `line_error` → `_pair_errors` associates
them with Y series → `ScientificSeries.error_column` and `error_kind` retain the pair → semantic
proposal lists the error column with its series → explicit semantic confirmation gates
`build_plan` → frozen Origin `plot_spec` retains the pair → Origin calls `layer.add_plot` with
`colyerr=series.error_column`.

The backend-neutral `render_spec` currently contains `data.x` and `data.y`, but no per-series
error data. Existing name recognition labels SD, SEM, SE, and custom error suffixes; CI and the
requested `explicit` label are not yet normalized. `_pair_errors` falls back to column order
after exact name matching, so multi-series error binding needs an explicit confirmation or a
strict ambiguity failure before Grapher rendering.

The installed Grapher 27 type library exposes `IAutoLinePlot.ErrorBars` and
`IAutoErrorBars.VertBarType`, `VertBarCol`, and `VertBarDirection`. It defines
`grfReadFromData = 1` and `grfBoth = 0`. A direct native COM probe saved a GRF and reopened it;
the three values persisted as `1, 3, 0`. The Script Recorder was not needed.

## Implemented contract

The existing `ScientificSeries.error_column/error_kind` remains the source of truth. The
confirmed RenderPlan adds `render_spec.data.y_errors` keyed by each Y column:

```json
{
  "Control": {"column": "Control_SD", "kind": "sd", "direction": "y", "symmetric": true},
  "Treatment": {"column": "Treatment_SD", "kind": "sd", "direction": "y", "symmetric": true}
}
```

Kinds `sd`, `sem` (including SE), `ci`, and `explicit` label the supplied numeric values;
neither backend calculates them. Multiple error columns that cannot be matched to series by
name now fail with `error_pair_ambiguous` instead of silently pairing by order. A single
remaining series and error column can still be paired. This is a deliberate tightening of
ambiguous mapping; existing verified Origin routes and tests passed.

Grapher stages X, Y series, then independent error columns. One `grapher_sciplot.error_bar`
capability sets the native `ErrorBars` properties for both line and scatter plots. Unsupported
X/asymmetric errors, missing/non-numeric errors, and missing plotted-row values fail with
structured codes. The backend reopens each GRF, reads native plot and error-bar column indices,
resolves the column names from the staged CSV, and verifies each Y/error pair. Origin continues
to use its existing `layer.add_plot(..., colyerr=series.error_column)` path.

Representative multi-series readback:

```json
{
  "plots": [
    {"y_column": "Control", "error": {"present": true, "column_index": 4, "column": "Control_SD", "direction": "y", "symmetric": true}},
    {"y_column": "Treatment", "error": {"present": true, "column_index": 5, "column": "Treatment_SD", "direction": "y", "symmetric": true}}
  ]
}
```

The Grapher verify report has `status: "ok"` and `checks.error_bindings: true`, in addition to
native file signatures, staging integrity, document reopen, plot bindings, axes, and legends.

## Native acceptance evidence

- `.phase4-e2e/line_single`, `.phase4-e2e/line_multi_02`, and
  `.phase4-e2e/scatter_single` retain native GRF, PNG, PDF, staging CSV, plan, manifest, and
  readback reports. The six requested delivery copies are at `.phase4-e2e/line_error_single.*`
  and `.phase4-e2e/line_error_multi.*`. PNG inspection showed vertical capped errors at the
  expected values.
- The same single and multi `line_error` RenderPlans rendered through Origin in
  `.phase4-e2e/origin_line_single` and `.phase4-e2e/origin_line_multi`, each with
  OPJU/PNG/PDF/TIF and successful Origin readback. The multi Origin report records
  `Control → Control_SD` and `Treatment → Treatment_SD`. Origin also rendered the new
  scatter-with-error plan through its existing renderer in `.phase4-e2e/origin_scatter_error`.
- Grapher integration: **6 passed** (three earlier XY routes, three error routes).
  Full non-GUI suite: **948 passed, 7 skipped, 7 deselected**. A final read-only verifier
  expression cleanup was followed by **25 focused tests passed**. No Origin renderer files changed.

The saved Grapher PNGs visibly show error bars and caps; native readback confirms that the GRFs
are editable plot objects. The error-bar strokes use Grapher's default black style rather than
the series colors. The existing Grapher scatter route also shows a thin connecting line in PNG
despite native plot line width reading zero; its phase-2 PNG had the same appearance. These
visual style issues do not affect series/error binding, but should be resolved before using the
capability as a publication style default for Bar charts. Origin's new line-error exports also
show top title/legend clipping; the Origin renderer was unchanged in this phase.

The user subsequently opened both retained `line_error_single.grf` and `line_error_multi.grf`
in Grapher GUI and confirmed the error bars are visible, mapped to the correct series, the
legend is normal, and the series remain manually editable. The native GUI acceptance gate is
therefore passed.

One later attempt to rerun the native Grapher test after a color-style change was rejected by
automatic approval review because the account had reached its usage limit. The unverified style
change was removed. The successful native results above were produced with the retained code.
