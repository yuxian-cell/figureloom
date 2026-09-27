# Phase 13 route inventory and coverage

## Inventory boundary

The authoritative route list is `TemplateRegistry.implemented()`: **41 public implemented Origin template routes**. `xps_adaptive` and `xps_c1s_fit` are two internal adapters behind the public `xps` route and are not counted again. ErrorBar, Fit, range and series count are composable variants of a template route, not independent registry IDs. Some templates have multiple plot modes; classification below covers the **whole** public template, including its optional modes. The generated [machine-readable matrix](route-coverage-phase13.json) records each registry ID, example mode, fixture, Origin runner, required capabilities, test-file evidence, and both backend statuses. Regenerate it with `python tools/build_route_coverage.py`. The generator fails if the A/B/C annotations drift from the public registry.

Origin routes dispatch through each manifest's `runner.py`; the common renderers include `scientific_renderer`, `categorical_renderer`, `evidence_renderer`, network and 3D renderers, plus the public XPS adapter selector. At the start of Phase 13, Grapher accepted only `scatter`, `trend`, `line_error`, and `bar` in `_prepare`: **4/41 = 9.8% raw template coverage**. Batch 1 adds `cv`, `lsv`, and `xas`, raising coverage to **7/41 = 17.1%** after native integration. The original four routes contain the MVP base combinations: Scatter, single/multi XY Line, symmetric Y Error, simple/grouped Bar, and native Linear Fit. `scatter` also supports native degree-2 Polynomial Fit. Grapher explicit weighted Linear Fit remains the **one confirmed `unsupported_backend_capability` semantic variant**; it is recorded separately from the 41 template IDs and returns `unsupported_fit_weighting`. The 34 remaining public templates are `not_implemented` (14 B routes) or `new_family_required` (20 C routes), not silently downgraded.

## A/B/C classification

| Category | Count | Public template IDs | Reason |
| --- | ---: | --- | --- |
| A — existing capability composition | 7 | `bar`, `cv`, `line_error`, `lsv`, `scatter`, `trend`, `xas` | Their full registered route uses the existing native XY or Bar object family and current Error/Fit composition. |
| B — thin backend adapter | 14 | `bland_altman`, `calibration_curve`, `decision_curve`, `diagnostic_curve`, `dsc`, `eis`, `ftir`, `horizontal_bar`, `nmr`, `paired_trajectory`, `percent_stacked_bar`, `pl`, `stacked_bar`, `xps_compare` | Needs a small axis, orientation, reference-line, stacking, or mode-specific translation before the full template can be claimed. No new Core scientific semantic is expected, but native behavior must be probed. |
| C — new family/capability | 20 | `bubble`, `circular_network`, `confusion_matrix`, `density_ridgeline3d`, `forest`, `grouped_box`, `heatmap`, `histogram`, `pie`, `radar`, `raincloud`, `raw_summary`, `sankey`, `shap_dashboard`, `shap_summary`, `trajectory3d`, `uv_vis`, `violin`, `xps`, `xrd` | Requires a new native object family, layered/inset layout, domain-specific relationship, or new readback/verify model. A simple submode does not make the whole template supported. |

The bundled fixtures show why visual resemblance is insufficient. `nmr`, `ftir` and `xps_compare` need a descending X axis; `uv_vis` can contain a Tauc inset; `xrd` includes Rietveld refinement; `pl` includes log-scale TRPL and ordinary spectra. These route IDs remain outside Batch 1. The registry has no explicit IDs for `scatter_error_fit` or `bar_grouped_error`; those are capability combinations of `scatter` and `bar`.

## Batch 1 decision, before implementation

Migrate `cv`, `lsv`, and `xas` as one **XY overlay family batch**. Their bundled examples produce `plot_kind=line`, linear X/Y scales, no ErrorBar or inset, and multiple existing source series. Each already normalizes to the existing `xy_line` RenderPlan without changing source data or inventing a Grapher plot enum in Core. `trend` supplies the renderer/readback/verify baseline. The batch introduces **zero new renderer families and zero new scientific capabilities**. Other A routes were already supported.

The first three have generic registry alignment tests but no route-specific test files today; Batch 1 must add explicit plan/dispatch tests and one isolated Grapher native render/save/reopen/readback/verify integration per route. A representative multi-line Grapher GUI artifact from Phase 10 already covers the underlying XY primitive, so repeated manual inspection is optional; native verification remains mandatory.

### Representative Grapher GUI matrix

| Native family / combination | Previously accepted representative | Batch 1 relationship |
| --- | --- | --- |
| XY Scatter + Linear Fit; Scatter + Error + Fit; partial range | Phase 10 GUI regression, 3/3 checked | Unchanged |
| Multi-line XY; multi-line + symmetric Y Error | Phase 10 GUI regression, 2/2 checked | CV, LSV and XAS reuse this family; their native readback/verify runs independently |
| Grouped Bar + Error | Phase 10 GUI regression, 1/1 checked | Unchanged |
| Quadratic native Fit | Phase 12 GUI acceptance | Unchanged |

The Phase 10 representative set was user-checked in native Grapher, 6/6 passed. The new routes were not separately opened in the GUI this phase; their GRF/PNG/PDF artifacts, native readback and isolated integration passed. The CV PNG was also visually inspected.

For a high-priority domain-route measure, the fixed denominator is `scatter`, `trend`, `line_error`, `bar`, `cv`, `lsv`, `xas`, `eis`, `pl`, `uv_vis` (10 routes). Coverage moved from **4/10 = 40%** to **7/10 = 70%**. This priority set is a product planning annotation, not a registry count. Separately, the seven MVP **capability families** named above already have representative native Grapher coverage; counting those rather than nearly identical route variants avoids inflating a family metric. The batch increases domain-template coverage and does not add an MVP primitive.

## Status rules

`supported` requires native editable GRF, PNG/PDF, save/close/reopen, readback, verify and isolated integration. `not_implemented` means the template is a plausible A/B mapping but production dispatch still rejects it. `new_family_required` means the registered template needs more than a thin adapter. `unsupported_backend_capability` is reserved for a confirmed native limitation, such as Grapher's explicit weighted Linear Fit. No route silently drops error, fit, axis or other scientific semantics. The matrix also supports `partial` and `experimental`, but neither is used to disguise an unverified full route.

`recommend` and `plan` currently remain engine-neutral. Final Grapher route validation occurs in `_prepare` before native rendering; an unlisted template returns `grapher_route_unsupported`, and explicit weighted Linear Fit returns `unsupported_fit_weighting` before any fallback. This keeps the existing Origin planner and output behavior unchanged. Engine-aware recommendation filtering can be considered in a later workflow phase; it is not required to maintain semantic safety at render time.

Grapher 27.1.296 can fail with a COM access conflict when many native tests run in one Python process. `tools/test_grapher_isolated.ps1` runs every Grapher-marked test in its own Python/Grapher process and checks for a newly remaining PID after each case. It never terminates a process, preserving user-owned Grapher sessions. Origin's crowded automatic Fit statistics box remains known visual debt.

## Batch 1 result

All three routes reuse Grapher's existing XY Line renderer, series loop, legend, axis styling, native save/export, readback and verify. No renderer was copied. Each uses the same scientific RenderPlan as Origin. The Grapher production dispatch changed only its supported template list.

| Route | Origin baseline | Grapher mapping | Native Grapher result | Explicit test |
| --- | --- | --- | --- | --- |
| `cv` | `scientific_renderer`, two cycles | `xy_line`, two existing Y series | GRF/PNG/PDF, reopen/readback/verify PASS; `Cycle 1`, `Cycle 2` | `test_batch_1_grapher_native_route[cv]` |
| `lsv` | `scientific_renderer`, two samples | `xy_line`, two existing Y series | GRF/PNG/PDF, reopen/readback/verify PASS; `Sample A`, `Sample B` | `test_batch_1_grapher_native_route[lsv]` |
| `xas` | `scientific_renderer`, two spectra | `xy_line`, two existing Y series | GRF/PNG/PDF, reopen/readback/verify PASS; `Sample A`, `Sample B` | `test_batch_1_grapher_native_route[xas]` |

Each Grapher test ran in its own Python/Grapher process, verified that its owned process exited, and used the route's bundled fixture. The three matching Origin baseline integrations passed with OPJU/PNG/PDF/TIF. The existing Phase 10 multi-line GUI artifact is the representative native XY family check; Batch 1 did not introduce another visual primitive. The CV production PNG was also visually inspected for its two line curves, legend, title and axis labels.

| Regression | Result |
| --- | --- |
| Batch 1 Grapher isolated | 3/3 passed |
| Batch 1 Origin | 3/3 passed |
| Full Origin native suite | 11 passed, 1021 deselected; exit code 0; COM teardown diagnostics observed |
| Full Grapher native suite, isolated | 20/20 passed; each case exited with zero new Grapher PIDs |
| Full non-GUI suite | 994 passed, 7 skipped, 31 deselected |

The Origin suite returned exit code 0 despite Windows COM teardown diagnostics. A post-suite process check found six `Origin64.exe -Embedding` processes started during that suite; their ownership was not proven, so this phase leaves them untouched and records Origin lifecycle cleanup as an open issue. Grapher's 20 isolated cases each ended without a newly remaining Grapher PID. The accepted single-process Grapher COM limitation remains.

Phase 13 Batch 1 will not be committed until the inventory, coverage and regression results have been reported to the user. After that report, choose either a second batch or Phase 14 workflow hardening based on high-value unmet routes rather than raw coverage percentage alone.
