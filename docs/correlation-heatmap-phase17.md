# Phase 17 — Correlation Heatmap Adaptive Layout & Annotation UX

**Status: COMPLETE — automatic verification, four-project GUI acceptance and
final Origin viewport GUI reopen spot-check PASS.**
Baseline: Phase 16 `8b6e98eca629ed6339db10596ee4bf85ea75ac79`. Version remains
0.1.0. No release, tag, Phase 18, generic heatmap or new statistical route.

## Problem and scope

The short `Demo_1`…`Demo_8` synthetic labels did not expose the real Concrete
9-variable layout failure. Fixed 45-degree rotation, fixed pages and shrinking
annotations caused long variable labels and value/star annotations to crowd.
The original six native Concrete workflows passed scientific verification;
that did not constitute visual acceptance. GUI inspection identified ordinary
annotation text with no special markup and a scale/readability problem.

Only the correlation submode changes. The existing generic heatmap layout
can thin labels and is deliberately not reused here. Fit, XY, Bar, ErrorBar,
statistics, matrix validation, thresholds, source order and color semantics
are unchanged. All labels, including underscores, are retained in full.

## Architecture and deterministic rule

`figureloom_engine/correlation_layout.py` computes physical inch/point layouts
beside the Core contract. `build_plan` freezes both backend layouts in the
hash-bound `RenderPlan.correlation_layout`; validation rejects stale layouts.
Renderers consume the selected backend layout. Older plans without this
optional field remain valid and get a newly computed layout when rendered;
verification of already saved older projects retains its prior contract.

Arial-like character advances are approximated in em units: narrow characters
0.30; wide ASCII 0.90; uppercase 0.70; digits/underscore/star/signs 0.60;
ordinary lowercase 0.56; full-width Unicode 1.00; combining marks zero.
Estimated physical width is the sum × font points / 72. No GUI font dependency
or image renderer is used. This is an estimate, not exact glyph metrics.

- Axis label font: 10 pt. Annotation: Origin 11 pt, Grapher 10 pt, including
  11–20 matrices; text never becomes smaller as the matrix grows.
- Cell side = ceil-to-0.01-inch(max(0.55 inch, longest displayed annotation
  width + 0.24 inch)). Disabled annotations do not reserve value/star width.
- Try 45°, 60°, 90° in order. Choose the first whose estimated horizontal
  projection fits cell side minus 0.12 inch. Long labels do not unconditionally
  force 90°; there are tests exercising all three selections.
- Plot span = N × cell side, square in physical inches on both backends.
- Left margin = longest label width + 0.40 inch. Bottom margin = rotated label
  height + 0.45 inch. Title reserve = 0.70 inch. Page grows around the plot.
- Separate native legend allocation: Origin 1.25-inch column, Grapher 2.25-inch
  column, separated by 0.35 inch. Grapher reserves at least 4.65 inches of
  height for all 21 native legend entries, including small matrices.
- `compact` identifies short labels at N≤8; `expanded` identifies larger/long
  labels. Neither profile means fixed page size. N>10 retains a density warning;
  the supported maximum remains 20. Large annotated matrices produce large
  physical pages, which must not be shrunk blindly to a journal-column width.

## Native implementation and readback

Origin retains one Matrix Heatmap, native 256-level cyan–white–red colormap,
native Spectrum scale, and native editable `CHX`, `CHY`, `CHC` text objects.
Geometry is converted from physical inches to percent-of-page layer bounds.
Text centers reserve full estimated label extents outside the plot. Spectrum
dimensions are set before its position and its labels are explicitly enabled;
the scale remains linked and fixed at [-1,1]. Scientific text stays ordinary
strings such as `-0.28***`; no superscript/rich-text workaround is introduced.

Grapher retains native Class Scatter, X=column+1, Y=N-row, 21 exact unchanged
intervals, square symbols, and linked Class Symbol Legend. Page/axes/symbols,
text positions and legend allocation consume the physical layout. Legend
entries use 9 pt, title 10 pt. Keep `correlation_cells.csv` beside the GRF.

Actual reopened native properties are recorded: page/plot dimensions, axis-label
font sizes, annotation sizes; Origin label rotation; Grapher text bounding boxes.
Layout verify checks square dimensions, fonts and native bounds. Grapher label
boxes must be on-page, below the plot and separated from their neighbors.

**Grapher COM limitation:** Text shape `Rotation` returned zero after setting
0/45/60/90, while its actual width/height and exported glyph rotation changed.
It behaves as a transformation rather than a reliable persisted text-angle
getter on this installation. We preserve the raw property as
`x_label_shape_rotation_deg`, do not mislabel it as the glyph angle, and never
substitute a RenderPlan value into readback. Planned angle is deterministic;
actual angle needs export/GUI review. Native boxes and sizes are still verified.

## Scientific evidence and fixtures

Matrix-only, supplied matrix + supplied p-values, and raw 1030-row Pearson
cases each execute canonical workflow → native render → save/close/reopen →
native readback → verify. Raw analysis uses the previously agreed SciPy Pearson
two-sided test, all rows, no correction; it is test/data preparation, not a new
production statistical engine. The raw user table is not committed. Optional
test source is `FIGURELOOM_CONCRETE_RAW`; absent source/SciPy means SKIP, not PASS.

Small supplied Concrete matrices are checked in with source explanation.
Anchors (abs tolerance 1e-13) are Cement–Strength 0.4978319193241571,
Water–Superplasticizer -0.65753290762845, Superplasticizer–Strength
0.36607882718852036 and Age–Strength 0.32887300077998355. Cell/star text,
p-values, orientation, native relationships and native exports remain checked.
External source SHA-256 is also recorded before and after final regression.

## Before/after dimensions (Concrete 9×9 with p-values)

| Backend | Before page (in) | After page (in) | Before plot (in) | After square plot (in) | Cell annotation | X angle |
| --- | --- | --- | --- | --- | --- | --- |
| Origin | 8.50 × 7.50 | 11.767222 × 10.917222 | 5.185 × 5.175 | 8.37 × 8.37 | 9 → 11 pt | 45 → 90° |
| Grapher | 7.40 × 6.10 | 12.227222 × 10.377222 | 4.00 × 4.00 | 7.83 × 7.83 | 9 → 10 pt | 45 → 90° |

Matrix-only profiles are smaller because stars do not require additional cell
width. No algorithm, r/p value or significance decision changes with layout.

| Matrix-only backend | Page after (in) | Square plot after (in) | Annotation | X angle |
| --- | --- | --- | --- | --- |
| Origin | 9.337222 × 8.487222 | 5.94 × 5.94 | 11 pt | 90° |
| Grapher | 9.977222 × 8.127222 | 5.58 × 5.58 | 10 pt | 90° |

All six final Concrete native cases have passed. For each A/B/C case, Origin
and Grapher's reopened matrices, p-values and annotation strings were compared
and match exactly; their native color representations remain intentionally
different. Full old-route regression is a separate gate below.

## Automatic regression and prior failures

Native counts, runtimes, residual process observations and representative output
paths are recorded below. Earlier development probes
are preserved, not promoted to passing results:

- First layout unit run: 51 passed, 1 failed (a test's medium-width expectation
  did not match the documented projection rule). Corrected test now covers
  the actual 45/60/90 rule.
- First Origin native probe: FAILED due to local scalar/dictionary variable
  shadowing. Corrected; isolated rerun passed. Origin cleanup emitted existing
  `0x800706be` diagnostic; no process was killed.
- First Grapher real-data probe: FAILED layout verification because the shape
  Rotation getter was incorrectly treated as a persisted text-angle getter.
  Corrected normalization to actual native boxes/raw property; rerun passed.
- Origin scale-placement prototype required resizing/position ordering and
  explicit scale-label visibility. Final probe reopens/verifies successfully.
- First full non-GUI regression: **1 failed, 1064 passed, 7 skipped, 42 deselected
  in 104.73 seconds**. The failure was the generated route inventory's test list:
  it lacked the two new heatmap test files. Regenerated with the existing tool;
  only those two test references changed, not route coverage or capabilities.
  Final full rerun passed: **1065 passed, 7 skipped, 42 deselected in 106.38
  seconds**. Native tests were deselected here and executed separately;
  skipped tests are not counted as passing. Layout unit tests: 25 passed.

Native process isolation and lifecycle code are unchanged. Origin processes
are observed only; process-name kill or PID-difference ownership is never used.
Grapher regression uses the existing per-node subprocess runner and checks
new residual PIDs without terminating them. Cross-backend tests run after the
Grapher suite to avoid overlapping Grapher instances.

Grapher isolated regression: **25 passed, 0 failed, 0 skipped**, 863.67 seconds
(14m23.7s); all 25 subprocess logs report one passing test and zero newly
remaining Grapher processes. The full collection is 25 native nodes; individual
node runs do not select/deselect the other nodes.

Origin isolated regression: **17 passed, 0 failed, 0 skipped**, summed native
case execution 967.57 seconds (16m7.6s), excluding cleanup waits, initial CV
keep-open pass and user wait. Each subprocess selects one exact node, so no
suite-wide deselection count applies. CV's existing
baseline test deliberately used the default `close_application=False`, leaving
its project visible after a passing assertion. The runner stopped rather than
terminating that window. The test now explicitly requests `close_application=True`
for isolated CV/LSV/XAS regression; production defaults are unchanged. After the
user closed the earlier window, CV rerun and all remaining nodes passed. Other observed
Origin instances exited naturally during bounded cleanup observation. These
observations are not COM activation failures or failed scientific assertions.
Final observation: zero Origin and zero Grapher processes. Existing
`0x800706be` cleanup diagnostics occurred in some passing Origin subprocess
logs and are retained; no force termination was used.

All six A/B/C native layout cases ran (zero skipped), included in the native
suite totals above, not six additional tests. Logs are in
`.phase17-origin-regression/`, `.phase17-grapher-regression/`,
`.phase17-nongui-final.log` (first run) and
`.phase17-nongui-final-rerun.log` (final run). Grapher isolated runner summary is
`.phase17-grapher-regression.log`; normalized Concrete evidence and hash records
are under `.phase17-records/`. The runtime manifest was regenerated; Ruff and
`git diff --check` pass.

All three external source SHA-256 values match the prior Concrete baseline and
the recorded before/after hashes; per-case fixture/raw integrity assertions also
passed. Full digests:

```text
concrete_correlation.csv b01057d53f4db5006c272085ee5ab45c4f3d45da405f911a019167b5226ba3a1
concrete_pvalues.csv     638d9f18148470021a8a296f686c318f315d8359a1cae17c1f59362c0db194ef
concrete_raw.csv         4698cfcf9dfa2d73acfb6c74cf0e77c382862da270f8d6a7ce95048d130ee007
```

## Manual GUI gate and remaining limits

Manual acceptance of all four final Concrete projects is **PASS**, reported by
the user after inspecting the actual Phase 17 projects. Origin's 9×9 cells,
complete long labels, 11 pt value/star annotations and native spectrum passed.
Grapher's values/stars, complete labels, non-overlapping annotations and
21-class legend passed after enlargement. This is user GUI evidence, not an
inference from automatic verification or the Phase 16 synthetic GUI gate.
Origin: check all cells, full long labels, distinguishable stars, no overlap,
native editable text/scale and matrix→color relation. Grapher: check native
Class Scatter/text, full long labels, stars, 21-entry legend and shared mapping.
Raw Pearson shares the p-value layout; automatic native testing is still required.

Four fixed manual validation projects (relative to repository root):

1. Origin matrix only:
   `.phase17-origin-regression/case-2/test_concrete_native_layout_ma0/origin/origin/result.opju`
2. Origin supplied p-values:
   `.phase17-origin-regression/case-3/test_concrete_native_layout_pv0/origin/origin/result.opju`
3. Grapher matrix only:
   `.phase17-grapher-regression/case-2/test_concrete_native_layout_ma0/grapher/grapher/result.grf`
4. Grapher supplied p-values:
   `.phase17-grapher-regression/case-3/test_concrete_native_layout_pv0/grapher/grapher/result.grf`

Each project folder contains native exports and its reopened verification report.
The raw counterparts are in each suite's `case-4/test_concrete_native_layout_ra0`.

Export review shows substantially more label and annotation room. Thin horizontal
marks above Origin text seen in previous exports were recorded during development;
the user subsequently confirmed annotation readability and distinguishable stars.
No markup/statistical claim is inferred
from them. Exact font metrics, arbitrary very long labels and reduction of a
large page to a small print column remain limitations. No pixel-perfect parity,
raster substitute, generic heatmap, clustering, abbreviation or EditPlan added.

Stop after automated verification and wait for GUI acceptance. No commit/release
or next phase is performed before that gate.

## Final Origin viewport UX patch

An adaptive physical page may exceed the graph child-window viewport. The
Concrete p-value page remains 11.767222 × 10.917222 inches: its plot, annotations
and physical page must not be shrunk to fit the screen.

Only the correlation heatmap renderer activates its completed native graph and
executes `win -z0;` immediately before saving `result.opju`. Origin documents
this as Fit page to window size ([native Window command reference](https://docs.originlab.com/labtalk/ref/window-cmd/)).
The existing export and save/close/reopen verification sequence is preserved;
verification does not re-save the project or replace its saved viewport state.
No shared lifecycle/helper or other route's window behavior is changed.

**Whole Page is a viewing state, not a substitute for physical adaptive layout.**
The user manually applied Ctrl+W (View → Whole Page), saved, closed and reopened
the earlier Phase 17 OPJU, and confirmed Whole Page persisted without changing
physical dimensions. The automated command received a separate final GUI reopen
spot-check, recorded below; the earlier manual command was not its acceptance.

Viewport state cannot be reliably read back programmatically with the currently
verified interfaces. A numeric zoom value is not proof of Whole Page mode. No
planned/cached mode is added to native readback or promoted to a passing check.
Physical page size, plot bounds, 11 pt annotations, 90° labels, science and native
spectrum remain checked by reopened native readback.

Final patch automatic checks: **27 non-GUI passed, 2 native deselected in 6.08s**;
**4/4 isolated Origin native passed, zero skipped**, summed subprocess execution
127.32s (synthetic, Concrete matrix-only, supplied p-values and raw Pearson).
All four jobs observed zero newly remaining Origin processes after bounded
cleanup; no unknown process was attached or killed. The existing cleanup
diagnostic in the passing synthetic test log is retained. No shared lifecycle
was touched, so this patch did not rerun the unrelated full Origin suite.

Representative new project:
`.phase17-origin-viewport/case-3/test_concrete_native_layout_pv0/origin/origin/result.opju`.
Its reopened physical page is **11.77 × 10.92 in**, annotation fonts are all
**11 pt**, and X-label rotations are all **90°**. Matrix, p-values, annotation
text, mapping, spectrum and native layout readback exactly match the previously
accepted p-value project. PNG/PDF/TIF and save/close/reopen/verify all pass.
All three external CSV SHA-256 values still match the baseline; the record is
`.phase17-origin-viewport/source-integrity.json`. Logs and subprocess summary
are under `.phase17-origin-viewport/`. Ruff and diff whitespace checks pass.

**Final automated viewport patch GUI reopen spot-check: PASS.** The user opened
the new representative OPJU and reported it has no issue, accepting the final
Whole Page viewport check on 2026-09-28. Phase 17 is approved for commit.
Version remains 0.1.0, with no tag, release or Phase 18 work.
