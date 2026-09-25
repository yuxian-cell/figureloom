# Phase 6: native linear-fit boundary and probes

Production rendering has no Fit route yet. Existing PL/XPS `series_role="fit"` means a **user-provided fit column** rendered as a line. The Origin scientific renderer selects plot type `l` for that series; it does not run regression or create an analysis operation. Existing scatter, line, error, and bar plans are unchanged.

## Contract and boundary

`editaplot_engine.fit_contract` defines `FitSpec` and `FitResult` independently of Origin and Grapher. `FitSpec.model="linear"` means `y = intercept + slope*x`; parameters have stable IDs `intercept` and `slope`. `ParameterSpec` reserves free/fixed, initial value, and bounds. `fit_range=None` means every valid source point; explicit bounds are X values, separate from displayed graph limits. `weight_mode="none"` is the first execution target; the schema reserves inverse Y, inverse Y², inverse sigma, inverse sigma², and explicit column weighting. `result_source` is one of `backend_native`, `core_computed`, or `imported`. Requested statistics and curve point count are presentation/output requests, not solver identity.

The Core owns model, column binding, range, weight convention, parameter policy, result source policy, and scientific verification. Each Engine maps the supported spec to its native analysis API and reads the native result. `FitResult` records model, named finite parameters, statistics, point count, range, weighting, backend, and result source. It does not yet modify `RenderPlan`; a future optional fit field can compose with the existing XY scatter/error renderer. Equation/R² labels on a graph are independent presentation options.

If an Engine lacks a requested native capability, return a structured code (`unsupported_fit_model`, `unsupported_fit_weighting`, `native_fit_not_supported`, `fit_create_failed`, `fit_execution_failed`, `fit_readback_failed`, `fit_result_invalid`, or `fit_source_binding_failed`). Never silently switch to Core calculation. A later explicit fallback may use `result_source="core_computed"`, with an honest provenance record and no claim of a recalculable native fit.

`FitCapabilities` is deliberately a small data contract. A dynamic `Engine.supports(...)` API is unnecessary until the first production Fit route needs to select an execution path. Future manifest/readback should store the spec, solver/application version, named parameters, statistics, native object existence, source binding, and editable/recalculation evidence. Raw Origin/Grapher object IDs belong only in backend metadata.

## Real probes

Both probes used `X,Y` rows `(1,2.1), (2,4.0), (3,6.2), (4,8.1), (5,9.9)` in an owned directory.

- Origin 2024, `originpro` 1.1.15: `LinearFit.set_data` + `report()` created a native FitLinear report and fit-curve worksheet. Saved OPJU, reset the owned project, reopened OPJU, and read the report, curve, graph, source worksheet, model, X/Y references, range, slope, intercept, and R². The report stores `y = a + b*x`, source A/B, and `[1*:5*]`. Parameter/statistic positions in the report are version-specific; the future route should use named result-tree fields where possible.
- Grapher 27.1.296: the installed Type Library identifies `AutoLinePlot.AddFit(grfLinearFit=0)` and `IAutoFitPlot`. The probe created a fit belonging to the original line/scatter plot, saved GRF, closed and reopened it, and read `Fits.Count=1`, `fitType=0`, X/Y columns 1/2, `MinX=1`, `MaxX=5`, and `UseCurveLimits=True`. Grapher's own `CopyStatsToClipboard` after reopen returned its fitted equation, point count, and R². The probe snapshots and restores every clipboard format; it aborts before copying if a format cannot be safely captured. This COM version's `Equation` property returned `0`, so native statistics text is the numerical readback source. The GRF refers to its CSV worksheet; keep GRF and CSV together.
- The user manually opened both project files and confirmed fit visibility, source relationship, editable fit settings, and ability to recalculate. This is GUI evidence, distinct from the programmatic checks above.

| Capability | Origin | Grapher |
|---|---|---|
| Native linear fit | Yes, FitLinear operation | Yes, AutoFitPlot child of XY plot |
| Editable fit object | Yes, GUI checked | Yes, GUI checked |
| Reopen preserving fit | Yes, OPJU readback | Yes, GRF readback |
| Slope / intercept / R² readback | Yes, native report | Yes, native statistics text |
| Fit range readback | Yes, report `[1*:5*]` | Yes, MinX/MaxX and UseCurveLimits |
| Regression weights | Not exercised | Not exercised; `SetWeight` is not proof of linear regression weighting |
| Parameter constraints | Origin API documents fixed slope/intercept; not exercised | Custom-fit API exposes parameter bounds; built-in linear constraints not established |
| Editable curve | Yes, GUI checked | Yes, GUI checked |
| GUI recalculation | Yes, user checked | Yes, user checked |

Native results on this fixture:

| Statistic | Origin | Grapher | Absolute difference |
|---|---:|---:|---:|
| slope | 1.9700000000000002 | 1.97 | 2.22e-16 |
| intercept | 0.14999999999999947 | 0.15 | 5.27e-16 |
| R² | 0.9988932358694533 | 0.99889324 | 4.13e-9 |

Grapher's text report rounds the displayed R² to eight decimal places. For a future first-version verification gate, require finite slope/intercept/R² and native object/source binding, then compare cross-engine reports at approximately `1e-6` absolute for slope/intercept and `1e-7` absolute for R² on this small fixture. Those are probe tolerances, not universal scientific uncertainty bounds. Define missing-value, weight, range, and R² conventions before extending the gate.

Recommended next production scope: one XY scatter series, full range, unweighted, free slope/intercept, no bands, native execution only. Add a Fit capability to the existing XY renderer; do not clone it into a separate scatter-fit route.

Official API references: [Origin LinearFit](https://docs.originlab.com/originpro/classoriginpro_1_1analysis_1_1LinearFit.html), [Origin FitLinear operation](https://docs.originlab.com/labtalk/guide/linear-fitting/), [Grapher AutoFits](https://grapherhelp.goldensoftware.com/auto_objects/LINK_AutoFits.htm), [Grapher fit plots](https://grapherhelp.goldensoftware.com/Graphs/Fit_Plots.htm), [Grapher statistics](https://grapherhelp.goldensoftware.com/Graphs/Fit_Statistics.htm).
