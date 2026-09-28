# EditaPlot v0.2.0 release notes

v0.2.0 adds the production **Correlation Heatmap** submode to the existing
Heatmap template. It retains inspect/understand → explicit confirmation →
canonical RenderPlan → native editable project → save/reopen/readback/verify.
See [Quickstart](quickstart.md) and [release verification](release-v0.2-checklist.md).

## Highlights

- Supplied square symmetric correlation matrices, with optional explicit
  p-value matrices. P-values are never inferred from correlation coefficients.
- Raw-observation Pearson workflow: explicit Python/SciPy data preparation
  computes Pearson coefficients and two-sided p-values, then the existing
  native workflow renders the frozen derived matrix. There is no direct raw
  Pearson CLI command or backend-native statistical calculation in this route.
- No multiple-comparison correction. Strict p thresholds are <0.001 `***`,
  <0.01 `**`, <0.05 `*`; diagonal cells never get stars.
- Fixed [-1,1] correlation color meaning: negative cyan, zero white, positive red.
- Native editable labels and value/significance annotations; native relationships
  survive saving, closing, reopening, readback and verification.
- Deterministic adaptive physical layout is frozen in RenderPlan. Matrix size,
  estimated label width, annotation/star text and legend footprint determine
  square cells, page size, margins and 45°/60°/90° X-label rotation. Full labels
  are retained; annotation fonts are Origin 11 pt and Grapher 10 pt.
- Origin applies Whole Page before final OPJU save. This saved viewport state
  does not replace or shrink the physical adaptive page.

## Native backend differences

| Shared semantic | Origin | Grapher |
| --- | --- | --- |
| `CorrelationHeatmapSpec` | Native Matrix Heatmap | Native Class Scatter with square cells |
| Color mapping | Continuous/native 256-level mapping | Explicit native 21-class discrete mapping |
| Native key | Spectrum/color scale linked to matrix plot | Class Symbol Legend shares cell class mapping |
| Editable output | OPJU + PNG/PDF/TIF | GRF + PNG/PDF + `correlation_cells.csv` |

Keep Grapher's `correlation_cells.csv` beside the GRF. Custom continuous Grapher
gradient mapping is **not production validated**. Backend visual pixels need not
match; labels, values, stars, orientation and color meaning must match.

## Real-data evidence

UCI Concrete Compressive Strength: **1030 complete finite observations × 9
quantitative variables**. No rows were dropped in this fixture. Supplied matrix,
matrix plus p-values and raw Pearson preparation × two native backends passed
**6/6**. All four representative GUI layouts and the final Origin Whole Page
reopen check passed. Native objects and matrix/class-to-color relationships
remained editable; long labels and `* / ** / ***` were readable without overlap.

Anchors: Cement–Strength 0.4978319193241571;
Water–Superplasticizer -0.65753290762845;
Superplasticizer–Strength 0.36607882718852036;
Age–Strength 0.32887300077998355. Source CSV SHA-256 values remained unchanged.

The Concrete p-value physical pages are Origin 11.77 × 10.92 in with an
8.37 × 8.37 in plot, and Grapher 12.23 × 10.38 in with a 7.83 × 7.83 in plot.
Matrix-only pages are Origin 9.34 × 8.49 in / 5.94 in square plot and Grapher
9.98 × 8.13 in / 5.58 in square plot. Origin's saved Whole Page view was manually
verified separately from these physical dimensions; viewport mode has no
currently reliable programmatic readback.

Historical engineering evidence: [Phase 16](correlation-heatmap-phase16.md),
[Phase 17](correlation-heatmap-phase17.md). Those records retain their original
0.1.0 development baseline; they are not rewritten as release notes.

## Known limitations

- This is correlation-specific, not arbitrary generic heatmap support. No
  clustering, dendrogram, triangular-only view, partial correlation,
  Spearman/Kendall, multiple-comparison correction or Heatmap AI EditPlan.
- Recommended size ≤10×10; 11–20 emits a density warning; hard limit 20×20.
  No abbreviation engine. Very long labels and downscaling to a small print
  column still require inspection at the intended physical output size.
- Raw preparation requires the caller to choose valid observations explicitly.
  The documented example requires finite numeric rows and rejects invalid data;
  it does not silently infer/drop missing values. SciPy is an optional analysis
  prerequisite, not a new runtime render dependency.
- Grapher has 21 discrete classes, not continuous-gradient parity with Origin.
  Its text-shape Rotation getter is unreliable; actual bounds are read back,
  and glyph angle was accepted manually. Keep the staging CSV with the project.
- Grapher uses isolated COM execution per job; long-lived single-process batches
  can conflict. Native explicit per-point weighted Linear Fit remains unsupported
  (`unsupported_fit_weighting`); Origin supports it. No silent fallback.
- Origin can emit `0x800706be` cleanup diagnostics and cannot always prove native
  process ownership. Safe exit/reference release is retained; unknown processes
  are never killed. Whole Page is a viewing state, not a layout workaround.
- Existing legacy Grapher Origin-route coverage remains **7/41**. Correlation
  Heatmap is documented separately as a production submode/family, not 8/42.
- Existing Fit/EditPlan scope, platform constraints and installer limitations
  remain as documented in [v0.1 notes](release-v0.1.md).

This release finalization creates a local annotated `v0.2.0` tag only. No push,
GitHub Release, package publication or Phase 18 is part of this operation.
