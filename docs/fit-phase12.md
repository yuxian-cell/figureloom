# Phase 12: native quadratic Polynomial Fit

Status: **native Origin and Grapher integration passed; GUI acceptance passed; isolated native regression accepted**. Scope is one X, one Y, XY Scatter, full range, unweighted, free coefficients, degree 2. Phase 13 has not started.

## Scientific contract

`FitSpec(model="polynomial", degree=2, x_column="X", y_column="Y")` serializes into the existing top-level `fit` object. It uses the existing free-parameter structure with `a0`, `a1`, and `a2`. The mathematical model is `Y = a0 + a1*X + a2*X^2`. `FitResult` contains `model="polynomial"`, `degree=2`, the three normalized coefficients, native R², point count, `weight_mode="none"`, `fit_range=null`, backend, and `result_source="backend_native"`. Existing Linear `FitSpec` and `FitResult` retain `slope`/`intercept` and omit `degree` when serialized.

The adapter rejects missing/nonintegral degree, any degree other than 2, weighted or partial-range polynomial fits, and multi-series polynomial fits. The fit requires at least three distinct valid X values. ErrorBar + polynomial is outside this first route. Phase 10 remains asymmetric: Origin supports explicit weighted **Linear** Fit; Grapher rejects it.

## Native implementations and evidence

| Backend | Native creation | Saved relationship and readback | Normalization |
| --- | --- | --- | --- |
| Origin 2024 | `FitPolynomial` X-Function via `xop`, `Order=2` | OPJU analysis lock, report and curve sheets; after reopen `op_change` returns `Order=2`, source X/Y and plot UID | Report `Intercept`, `B1`, `B2` → `a0`, `a1`, `a2` |
| Grapher 27.1.296 | Existing XY plot `AddFit(grfPolynomialFit=5)`, `Degree=2` | GRF `AutoFitPlot` with `fitType=5`, `Degree=2`, source plot's X/Y column indices; linked native Statistics shape exported as SVG after reopen | `Degree 0`, `Degree 1`, `Degree 2` → `a0`, `a1`, `a2` |

Grapher's installed COM Type Library identified `grfPolynomialFit`, `Degree`, and the `IAutoFitPlot` object. Live COM probes confirmed creation and persistence. Origin's installed `originpro` exposes LinearFit but no PolynomialFit class, so the small adapter calls the native `FitPolynomial` X-Function. Script Recorder was not needed. Neither production path computes coefficients or samples a curve in Python. The existing Scatter renderer, export, and project lifecycle are reused.

The fixed source is `X,Y = (-2,9), (-1,4), (0,1), (1,0), (2,1), (3,4)`. The independent exact reference is `a0=1`, `a1=-2`, `a2=1`, R²=1, n=6. On the same data a Linear least-squares reference gives intercept 3.666666667, slope -1, R²≈0.319148936. Independent native Linear renders returned Origin `(intercept=3.6666666666666665, slope=-1, R²=0.31914893617021284)` and Grapher `(intercept=3.6666667, slope=-1, R²=0.31914894)`. The quadratic relationship is visibly distinct. The reference computation is used only for verification, never production render.

| Result | a0 | a1 | a2 | R² | n |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reference | 1 | -2 | 1 | 1 | 6 |
| Origin native | 1.0000000000000007 | -2.000000000000001 | 1.0000000000000002 | 1 | 6 |
| Grapher native | 1 | -2 | 1 | 1 | 6 |

Origin's maximum absolute coefficient difference is about `8.9e-16`; Grapher's is `0` at native statistics display precision. The corresponding relative differences are below `1e-15` for nonzero reference coefficients. Both fits use all six points.

## Save, reopen, readback, verify

The production flow saves the editable project, closes the native application, reopens the saved project, reads the native fit relationship and statistics, then verifies the model, degree, source columns, curve, scatter, finite coefficients, R², exports and backend-native provenance. The stable GUI artifacts are:

- Origin: `.phase12-acceptance/origin/result.opju`, plus PNG/PDF/TIF.
- Grapher: `.phase12-acceptance/grapher/result.grf`, plus PNG/PDF. Its `grapher_staging.csv` remains beside the GRF.

Representative normalized readback, omitting unrelated presentation fields:

```json
{
  "origin": {"object_type": "FitPolynomial analysis", "native_degree": 2, "operation_binding": {"x": "[Book2]Sheet1!A\"X\"", "y": "[Book2]Sheet1!B\"Y\"", "plot_uid": 841}, "result": {"model": "polynomial", "degree": 2, "parameters": {"a0": 1.0000000000000007, "a1": -2.000000000000001, "a2": 1.0000000000000002}, "statistics": {"r_squared": 1.0}, "n_points": 6, "result_source": "backend_native"}},
  "grapher": {"object_type": "AutoFitPlot", "native_fit_type": 5, "native_degree": 2, "source_x_column_index": 1, "source_y_column_index": 2, "statistics_readback_source": "native_linked_text_svg", "result": {"model": "polynomial", "degree": 2, "parameters": {"a0": 1.0, "a1": -2.0, "a2": 1.0}, "statistics": {"r_squared": 1.0}, "n_points": 6, "result_source": "backend_native"}}
}
```

Both `origin_fit_verify_report.json` and `grapher_verify_report.json` in those output directories have `status="ok"`. The user inspected both saved projects in the native GUIs and reported acceptance, then closed the applications. Grapher's Degree control allowed 1–3 but did not accept a value above 3; this does not affect the supported degree-2 contract. No claim is made that EditaPlot supports degrees 1 or 3.

Representative verify summaries from the saved artifacts:

```json
{"origin": {"status": "ok", "checks": {"native_fit": true, "artifact_reopened": true}}, "grapher": {"status": "ok", "checks": {"document_reopened": true, "plot_binding": true, "native_fit": true, "legend_labels": true}}}
```

## Regression and limitations

- Phase 12 focused non-GUI tests: 27 passed, 2 native tests deselected. The final full non-GUI, Origin, and Grapher suite counts are recorded below after the final runs.
- Origin's automatic Fit statistics box remains crowded. This is the known Phase 11 visual debt and was not altered.
- Grapher native statistics readback uses its linked Statistics object exported to SVG; it does not use clipboard text. Native COM does not expose the polynomial coefficient values directly in the installed Type Library.
- The real COM libraries have emitted Windows teardown diagnostics while isolated pytest cases still exited successfully and reopened project verification passed. A separate two-render Grapher probe in one Python process produced an access violation on its second instance. Two full Grapher suite attempts crashed after earlier Grapher tests; a third crashed when starting the new polynomial case. These are failed single-process runs. All 17 Grapher native cases passed in separate Python processes, including the legacy routes and new polynomial case. The committed Phase 11 baseline also emitted `0x800706ba` diagnostics in a five-case sequence, though it exited with 5 passed. The user explicitly accepted 17/17 per-case process isolation as the Phase 12 native regression gate while this Grapher COM limit remains documented.

## Final test runs

| Run | Result |
| --- | --- |
| Full non-GUI regression | 990 passed, 7 skipped, 25 deselected |
| Phase 12 Origin native integration | 1 passed |
| Phase 12 Grapher native integration | 1 passed |
| Full Origin native suite | 8 passed, 1014 deselected |
| Grapher native cases in separate Python processes | 17 passed, 0 failed |
| Grapher native suite in one Python process | FAILED: COM access violation after several cases; accepted limitation, not counted as pass |

Capability matrix: Origin and Grapher both support native Linear Fit, partial-range Linear Fit and native quadratic Polynomial Fit. Origin supports explicit weighted Linear Fit; Grapher does not. Degree 3, weighted polynomial, partial-range polynomial, multi-series polynomial, and other models remain unsupported by EditaPlot.
