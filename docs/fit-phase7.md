# Phase 7: production Scatter + Linear Fit

`RenderPlan.fit` is an optional Phase 6 `FitSpec`. `editaplot plan --fit-spec-json fit.json` freezes it into the plan and its hash. Without `fit`, the existing Scatter, Error, Line, Bar, and Origin routes keep their previous behavior. The first production Fit capability accepts one XY Scatter series, all points, no weighting, free slope and intercept, and `requested_statistics=["r_squared"]`. Unsupported combinations fail before either application starts.

The existing Grapher XY renderer creates its Scatter plot, then adds `AutoLinePlot.AddFit(0)` to that plot. The saved GRF contains a native `AutoFitPlot` child; the base Scatter connecting line remains disabled. After reopening, verification reads its parent, X/Y columns, curve limits, native fit type, legend, and Grapher's own statistics. The GRF refers to the exported staging CSV; keep the files together.

The existing Origin Scatter worker creates the OPJU. `OriginEngine` then reopens it in a separately owned Origin instance and attaches `originpro.LinearFit.set_data(...).report()` to the existing worksheet, adds the native fit curve to the graph, saves OPJU, and exports PNG/PDF/TIF. Verification reopens a temporary OPJU copy so a user-opened project cannot block the check. It reads the native FitLinear report and curve worksheet, model, source X/Y references, fitted range, slope, intercept, R², and point count. Origin's report layout and Grapher's English statistics text are version-specific readback surfaces.

Both backends return `FitResult.result_source="backend_native"`; there is no numerical fallback. `fit-manifest.json` records the spec, application version, and native readback. `render-result.json` and the engine verify report carry the result. A readable native fit object and its source relationship are required for verification.

The deterministic fixture is `X,Y` with rows `(1,2.1), (2,4.0), (3,6.2), (4,8.1), (5,9.9)`. Origin 2024 returned slope `1.9700000000000002`, intercept `0.14999999999999947`, R² `0.9988932358694533`; Grapher 27.1 returned `1.97`, `0.15`, and `0.99889324`. Absolute differences are about `2.22e-16`, `5.27e-16`, and `4.13e-9` respectively. Grapher rounds its displayed R².

Real integration tests: `pytest -q tests/test_fit_integration.py`. Existing Grapher route regression: `pytest -q tests/test_grapher_engine_integration.py`. The COM tests are marked and skip on machines without the corresponding application. The default test run can exclude GUI tests with `-m "not grapher and not origin"`.

GUI acceptance: the user opened the final `.phase7-production/origin/result.opju` and `.phase7-production/grapher/result.grf` in their respective applications and confirmed that both native Fit objects can be selected, edited, and recalculated. The Grapher legend is normal. This is manual editability evidence in addition to the independent programmatic reopen/readback checks.

This route does not implement Error + Fit, weighted or constrained fitting, polynomial or nonlinear models, confidence bands, or multiple fit curves. The next useful check is Error + Fit because it exercises composition of the two existing capabilities without adding a new solver.
