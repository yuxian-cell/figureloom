# Phase 11: independent native Linear Fits per XY series

Status: **completed; native automation and both GUI independence checks passed**.

The existing `trend` XY line renderer accepts a list of the existing `FitSpec`
objects in top-level `fit`, in the same order as `render_spec.data.y`. A legacy
single FitSpec object remains unchanged. Phase 11 accepts two or more Y series,
full range, no weights, free slope/intercept, and `backend_native` only. It
rejects partial range, explicit weights, and shared/coupled parameters for the
multi-series case. Phase 10 capability asymmetry is unchanged: Grapher still
returns `unsupported_fit_weighting` for explicit weighted Linear Fit.

The two native backends attach one Linear Fit to each existing XY plot. Origin
persists separate `FitLinear` reports and curve worksheets in one OPJU;
Grapher persists separate `AutoFitPlot` objects in one GRF. Readback and verify
match each fit to its source Y column and compare native slope, intercept, R²,
and point count with an independent test oracle. No computed Fit curve is used
in production.

| Series | Origin slope | Origin intercept | Origin R² | Grapher slope | Grapher intercept | Grapher R² |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Control | 1.97 | 0.15 | 0.998893235869 | 1.97 | 0.15 | 0.99889324 |
| Treatment | 2.97 | 1.19 | 0.998969422424 | 2.97 | 1.19 | 0.99896942 |

Both native projects saved, closed, reopened, and passed programmatic readback
and verify. Each fit used five points. Grapher's legend contains both series
and both fitted curves. Origin's two report and curve references are distinct.

The first Origin GUI acceptance **failed**: `FitLinear2` reported Treatment
numerically, but its saved analysis operation carried Control's graph plot UID.
Report values alone did not prove independent recalculation. The Origin adapter
now sets each operation's `PlotObjUID` to its source plot and verifies the saved
operation's X, Y and plot UID after reopening. The new native integration passes:
Control uses UID 841 and Treatment uses UID 842.

Current GUI acceptance artifacts:

- Origin: `.phase11-e2e-uid2/test_origin_independent_native0/origin/result.opju`
- Grapher: `.phase11-e2e-final/test_grapher_independent_nativ0/grapher/result.grf`

Grapher GUI acceptance: **PASS**. The user modified Control and recalculated
only `Linear Fit - Control`; `Linear Fit - Treatment` remained unchanged and
bound to Treatment. After restoring Control, saving, closing, and reopening,
both native Fit relationships remained editable.

Origin GUI acceptance: **PASS on the repaired OPJU**. The report-sheet analysis
locks bind `FitLinear1` to Control and `FitLinear2` to Treatment. Modifying only
Control and recalculating its native Fit left Treatment's parameters and curve
unchanged. After restoring Control, saving, closing and reopening, both native
relationships remained editable. This supersedes the failed GUI acceptance of
the earlier `.phase11-e2e-final` artifact.

Before the binding fix, Phase 11 native integration reported 2 passed and the
non-GUI regression reported 988 passed, 7 skipped, 23 deselected. The first
full native run had two Origin single-Fit readback count regressions (21 passed,
2 failed); the affected legacy cases and new multi-Fit case passed after
selecting the correct graph for each readback mode (3 passed). The repaired
Origin native integration passed (1/1). The repaired non-GUI regression passed:
988 passed, 7 skipped, 23 deselected. Grapher native regression passed:
16 passed, 1002 deselected. Origin native regression passed: 7 passed,
1011 deselected. Ruff and `git diff --check` passed.
