# Phase 10: explicit direct weights

**Status: COMPLETED AS CAPABILITY RESOLUTION.** Origin 2024 supports native
explicit direct-weight Linear Fit. Grapher 27.1.296 does not expose that
native capability. Cross-backend parity is **not available**; this is a
backend capability limitation, not a failed test or an implementation bug.
The engine-neutral RenderPlan retains the FitSpec weighting semantics.
`FIT_CAPABILITIES` in `figureloom_engine.fit_contract` reports `native_linear`,
`partial_range`, and `explicit_weight`; both engine `doctor` reports include
this Fit capability snapshot. Grapher rejects an explicit weighted FitSpec
before COM activation with `unsupported_fit_weighting`, `engine=grapher`,
`requested_capability=explicit_weighted_linear_fit`, and
`native_support=false`.

`FitSpec` stores `weight_mode="column"`, `weight_column="W"`, and
`weight_interpretation="direct_weight"`. The scientific meaning is to minimize
`Σ W_i (Y_i - intercept - slope·X_i)²`, with finite, positive W values. W belongs
to FitSpec; the Scatter mapping marks it `ignored`, and an optional `Y_SD`
remains a separate error bar. The source CSV is read only.

Origin 2024's native `FitLinear` accepts W as its ED input and
`Fit.ErrBarWeight=1` selects **Direct Weighting**. The initial saved OPJU
contained a native W source binding. Reopen and readback checked that binding,
all five Scatter points, the native fit curve and result, and independently
compared slope, intercept, and weighted R² with the direct WLS equation. For the fixture
`(X,Y,W)=(1,2,10),(2,4,10),(3,6,10),(4,8,10),(5,20,0.1)`, unweighted
Origin returns slope `4`, intercept `-4`, R² `0.8`; direct weighted Origin
returns slope `2.0492610837438425`, intercept `-0.09852216748768505`, R²
`0.9557092049747067`. Origin uses weighted centered total sum of squares for
that R², matching the test oracle.
[Origin's Linear Regression dialog documentation](https://docs.originlab.com/origin-help/lr-dialog/)
defines Direct Weighting as the selected Error column's raw value in
`Σ w_i residual_i²`.

GUI inspection of the initial `Scatter + Y_SD ErrorBar + Fit` OPJU found that
Change Parameters still selected `Y_SD` as an unchangeable Y Error input. A
separate in-project weighted-fit worksheet has therefore been added so the
native Fit can bind X/Y/W independently of the plotted error bar. This change
passed automated OPJU save/reopen/readback/verify in
`.phase10-e2e/origin-staging-production`. The new OPJU's graph-based Change
Parameters entry still showed Book2 X/Y/Y_SD. The native report binding, by
contrast, is Book3 X/Y/W. The report-sheet analysis lock opens the saved native
Fit operation: the user confirmed Book3 W with Direct Weighting there. Changing
the last W from 0.1 to 20 changed the native slope/intercept from about
2.04926/-0.09852 to 4.5/-5; restoring W restored the original fit. All five
scatter points and Book2 Y_SD error bars remained intact. The final
save/close/reopen GUI check confirmed the report-sheet analysis lock still
binds Book3 W and retains Direct Weighting.
[Origin's recalculation documentation](https://docs.originlab.com/origin-help/analydialog-recalculate/)
identifies the report-sheet operation lock as the way to reopen the saved
analysis settings.

Grapher 27.1's registered Type Library exposes `SetWeight`, `LoadWeights`,
and `SaveWeights` for **Weighted Average Fit**, a distinct fit type from Linear
Fit. A real `Linear Fit` rejects `SetWeight(1,10)` with `Value must be >= 1 and
<= 0`; its statistics remain slope `4`, intercept `-4`, R² `0.8` after GRF
save and reopen. No per-point W binding is exposed by the Linear Fit object.
The Grapher GUI Property Manager was also checked on this installation; it
has no per-point weight setting for Linear Fit.
[Grapher's Fit Plot documentation](https://grapherhelp.goldensoftware.com/Graphs/Plot_-_Fits.htm)
describes its Weights section only for the separate Weighted Average fit,
where weights apply to positions within a running window.
Until a native Linear Fit weighting mechanism is demonstrated, the Grapher
engine rejects this FitSpec before COM activation with
`unsupported_fit_weighting`. It does not draw a precomputed curve or claim a
backend-native weighted result.

Grapher production Fit statistics readback now uses a native linked text
object created by `InsertStatistics(x,y)` on the reopened GRF. The text object
points back to the native Linear Fit. Grapher's own SVG exporter resolves its
`<<Equation>>`, `<<NumberOfPts>>`, and `<<R2_0>>` tokens to numeric text. The
backend reads that temporary SVG and deletes the temporary text object before
closing the unsaved document. No clipboard operation is used in production or
the real Fit probe. This path passed the complete Grapher real integration
suite: **15 passed** (Fit, partial range, error bars, line family, bar family,
and smoke). The user also opened six representative GRFs and confirmed the
Scatter connecting line stays off, native Fit and legend remain editable,
partial range persists, per-series error bars remain attached, and grouped
bars remain editable: **6/6 GUI checks passed**.

## Status

- **PASSED:** FitSpec/direct-weight validation; Origin direct-WLS numeric
  result; Origin staging render → native Fit → OPJU save/reopen → native
  readback → verify, GUI W edit/recalculate/restore/save/reopen acceptance,
  and final Origin native integration suite **6 passed**; Grapher non-clipboard
  Fit readback, final Grapher native integration suite **15 passed** (4 Fit,
  10 real routes, 1 smoke), and 6/6 GUI checks; final non-GUI regression
  **987 passed, 7 skipped, 21 deselected**. The Grapher explicit-weight
  fail-fast test is included in the non-GUI count.
- **UNSUPPORTED BY NATIVE BACKEND:** Grapher 27.1 native Linear Fit cannot bind
  an explicit per-point W column. Cross-backend parity is unavailable;
  `unsupported_fit_weighting` is returned before COM activation. Opening
  Origin Change Parameters from the graph also showed Book2 `Y_SD`; that
  entry does not expose the saved Book3 weighted-fit operation. The report
  sheet's analysis lock did expose, recalculate, and persist it.
- **NOT RUN:** Grapher native weighted Linear Fit integration, since this
  installation does not expose the required capability. No weighted GRF or
  weighted Grapher FitResult is claimed.
- **BLOCKED BY USAGE LIMIT (earlier turn):** An automatic approval could not
  complete because the account usage limit was reached. The requested COM
  retest was **not run** then. This was an approval interruption, not a
  security denial or a COM test failure. Subsequent COM tests completed.

Phase 10 capability resolution is complete under the accepted backend
asymmetry. Partial-range plus weighting, multi-series fit, and derived weights
remain out of scope.

## Phase 10B: Grapher 27 capability audit (2026-09-26)

Installed Grapher version: **27.1.296**. Repeatable read-only type-library
inventory: `tools/probes/grapher_typelib_inventory.py`; full 357-type output:
`.phase10b-evidence/grapher-typelib.json`. Live COM probe of a saved native
Linear Fit (`fitType=0`): `tools/probes/grapher_dispatch_probe.py`; output:
`.phase10b-evidence/grapher-live-dispatch.json`. The live probe closes its
unsaved GRF and the isolated application; it now refuses to start while
another Grapher process is open.

| Surface | Evidence |
| --- | --- |
| GUI | Direct Grapher 27 Property Manager inspection found no per-point Weight/Weight Column on Linear Fit. |
| Script Recorder | User-saved `.phase10b-evidence/grapher-fit-recorder.bas` records native `LineScatterPlot_obj.AddFit(grfLinearFit)` with no weight argument, column binding, or subsequent weight call. This records the tested Linear Fit creation path; by itself it does not prove the absence of every possible UI command. |
| `IAutoFitPlot` Type Library | All 13 methods and 36 properties enumerated. No `WeightColumn`, `Weighting`, `Sigma`, `Variance`, `Uncertainty`, or regression data-column property. `SetWeight`, `LoadWeights`, and `SaveWeights` are documented for Weighted Average Fit window orders. |
| Live Fit `IDispatch` | `GetTypeInfo(0)` is unavailable; `GetIDsOfNames` rejects `Weight`, `Weights`, `WeightColumn`, `Weighting`, `Sigma`, `Error`, `ErrorColumn`, `Variance`, `Instrumental`, `Uncertainty`, `Regression`, `Data`, and `Column`. It resolves `SetWeight`, but `SetWeight(1, 10)` is rejected on native Linear Fit (`fitType=0`: `Value must be >= 1 and <= 0`) and accepted on native Weighted Average Fit (`fitType=9`). The isolated probe closed its unsaved document and application. |
| Other native objects | `IGraph.CreateFit` exposes fit type, limits, interval and drawing arguments but no weight binding. `IAutoLinePlot.ErrorBars` is a separate display object. `IWksStatistics` computes per-column descriptive statistics, not a regression. The library lists no separate regression/analysis coclass. Installed `Fit Curve Properties.BAS`, `3D Fit Curve Properties.BAS`, and `WksStatistics.BAS` expose no weighted Linear Fit call. |
| Official model descriptions | Grapher defines Linear Fit as ordinary least squares. Weighted Average applies order weights within a moving window; LOESS uses local smoothing weights and RMA minimizes perpendicular distance. None matches explicit direct per-point WLS. |

[Available Fits](https://grapherhelp.goldensoftware.com/Graphs/Available_Fits.htm),
[Fit Plot properties](https://grapherhelp.goldensoftware.com/Graphs/Plot_-_Fits.htm),
[Worksheet Statistics](https://grapherhelp.goldensoftware.com/wks-DLG_STATISTICS.htm),
[Error bars and confidence intervals](https://support.goldensoftware.com/hc/en-us/articles/360019541554-Error-bars-confidence-intervals-in-Grapher),
[Script Recorder](https://grapherhelp.goldensoftware.com/command/developer/Script_Recorder.htm).

Minimal capability matrix for the existing Fit contract:

| Engine | Native Linear Fit | Partial X range | Native explicit per-point direct weights |
| --- | --- | --- | --- |
| Origin 2024 | true | true | true |
| Grapher 27.1.296 | true | true | false |

**Decision B:** No native explicit per-point weighted Linear Fit entry was
found in Grapher 27.1.296 across the inspected GUI, recorder, Type Library,
live `IDispatch`, other native objects, and official model definitions.
`native_explicit_weighted_linear_fit = false` for this installed backend.
No Grapher weighted GRF was produced, so native weight persistence,
recalculation, and readback are **not applicable**, rather than passed.
Cross-backend parity is unavailable by product decision. No fallback curve is
implemented. Grapher Weighted Average Fit is not explicit weighted Linear
regression.
