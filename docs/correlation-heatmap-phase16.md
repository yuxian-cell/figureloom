# Phase 16 — Native Correlation Heatmap

Status: **ACCEPTED: automated regression and both representative native GUI gates passed.** Baseline: 0.1.0,
`01b1dffdc9bddb0c90771df59f4d921dfba8190d`.

## Capability investigation (before production changes)

The Desktop `Gcorrelation_Grapher_demo` is an explicitly synthetic layout
experiment. It contains a native Class Scatter Plot, square symbols, native
text annotations and a decorative rectangle color bar. Its placeholder stars
are not p-values. The decorative bar and placeholder stars cannot be used as
the production scientific contract.

Origin 2024: a real matrix-backed Heatmap saves and reopens. `DataPlot.GetDatasetName()`
resolves the actual native matrix; `to_np2d()` recovers its values. Native
`layer.cmap` levels and colors persist, and `spectrum1` is the linked native
color scale. A 256-level cyan/white/red map was set, saved, reopened and read
back successfully. This is native colormap level mapping, not a claim of
infinitely continuous interpolation; Origin is not reduced to Grapher's 21 bins.

Grapher 27: XY Scatter exposes a numeric fill-color column, Gradient and
ColorScale. A predefined Gradient with fixed [-1,1] limits saves and reopens.
Thus Grapher is **not** declared incapable of continuous gradient mapping.
However, custom `SetColor` typed-array calls failed, a custom CLR file path
was rejected by `Gradient.Name`, and the installed Gradient interface exposes
node counts but no node-color getter. Custom continuous mapping with complete
native color readback is not yet production-verified.

Class Scatter offers a verified alternative: custom interval bounds, individual
square fill colors and a native class legend. After reopening the GRF, legend
entries retain `EntryDefault=true` and actual class intervals. The native plot's
`DisplayWorksheet().Range(...).Value` returns the plotted worksheet values;
production readback need not parse the source CSV or clipboard.

Evidence: `.phase16-probes/origin_native_report.json`,
`origin_colors_report.json`, `grapher_continuous_report.json`,
`grapher_custom_report.json`, `grapher_data_report.json`. These are development
probes, not production integration acceptance.

References: [Origin CMap object](https://docs.originlab.com/labtalk/ref/layer-cmap-obj/),
[Grapher Gradient](https://grapherhelp.goldensoftware.com/auto_objects/AutoGradient_Object.htm),
[Grapher SetColor](https://grapherhelp.goldensoftware.com/auto_q-z/SetColor-Method.htm).

## Boundary and implementation decision

Reuse the existing `heatmap` template with an explicit correlation submode in
the canonical RenderPlan. A backend-neutral CorrelationHeatmapSpec owns matrix
validation, significance and annotation formatting. The backends own native
objects, colormap translation, layout, exports and reopened object readback.
Generic Grapher Heatmap remains unsupported; supporting this submode must not
inflate generic route coverage. No second Engine or EditPlan architecture is
introduced.

## Production schema and input

The canonical RenderPlan has one optional `correlation_heatmap` object:

```json
{
  "labels": ["Demo_1", "Demo_2"],
  "correlation_matrix": [[1, -0.73], [-0.73, 1]],
  "p_value_matrix": [[1, 0.005], [0.005, 1]],
  "display": "full_matrix",
  "color_scale": {"min": -1, "max": 1, "type": "diverging", "palette_id": "correlation_diverging"},
  "annotation": {"show_value": true, "decimals": 2, "layout": "single_text"},
  "significance": {
    "enabled": true,
    "thresholds": [{"p": 0.001, "text": "***"}, {"p": 0.01, "text": "**"}, {"p": 0.05, "text": "*"}],
    "comparison": "strict_less_than", "diagonal": "none"
  },
  "title": "Synthetic correlation example"
}
```

The source is a CSV/XLSX wide matrix: the first column contains row labels;
the remaining headers contain the same ordered labels. Its values must match
the frozen matrix exactly. P-values are explicitly supplied in the same
ordered specification; they are never calculated from correlations. The
committed 8×8 fixture is a positive-definite signed AR(1) matrix. Its p-values
are synthetic threshold test inputs, not experimental inference.

Validation requires unique nonempty labels, square size 2–20, finite numeric
correlations in [-1,1], symmetry and diagonal-one tolerance `1e-10`, and
p-values of the same shape in [0,1]. No clamping, interpolation, silent
symmetrization, rescaling, or automatic star inference occurs. Significance
uses strict `<` comparisons, strongest threshold first; diagonal stars are
suppressed. Supplying p-values does not implicitly enable significance.

## Native mapping and layout

Core logical cells are `(row, column, r, p, annotation)`; Grapher positions are
`x=column+1`, `y=N-row`. Origin uses its native matrix with a reversed Y axis,
placing logical row zero at the top. Combined native text displays, for
example, `-0.73**`. Both backends use square cells, rotated X labels, horizontal
Y labels and native text annotations.

Origin uses one real matrix Heatmap, 257 boundaries and 256 native color
levels, fixed [-1,1]. Its `spectrum1` scale belongs to that plot's colormap and
has major labels -1, 0, +1. It is not a decorative rectangle series.
Grapher uses one native Class Scatter Plot (type 32), square symbols and
white symbol outlines. Its native class variable is worksheet column 3,
Correlation; X/Y are columns 1/2. All 21 native class legend entries use
`EntryDefault=true` to preserve their class relationships.

Grapher bins are centered on -1,-0.9,…,0,…,+0.9,+1. Boundaries are
`[-1,-0.95,-0.85,…,0.85,0.95,1]`; intervals are left-inclusive and
right-exclusive. The final native upper boundary is `nextafter(1,+inf)` so
that +1 belongs to the final bin. Readback verifies this exact boundary,
every RGB fill and symbol identity. Quantization is explicit and auditable;
this is **discrete mapping**, not a continuous gradient claim.
The native legend rounds its last upper boundary to `<1`; its title explicitly
states `+1 included`. The exact exclusive native boundary is retained and
verified. `GetClassName` is only valid for name classification, not interval
classification; an attempted interval-name probe failed and was removed.

## Native readback and verify

After save → close → reopen, Origin resolves the native DataPlot's matrix
relationship and reads matrix values, native labels, annotations, colormap
levels/colors and native spectrum range. The graph has a hidden native
reference to its embedded p-value/cell-semantics worksheet. Grapher reads
the reopened native plot's `DisplayWorksheet` values, its X/Y/class column
assignments, class intervals/fills/symbols, text objects and class legend.
Neither backend reads numerical results from clipboard, original CSV, or
RenderPlan cache. The plan is only the expected comparator.

Normalized readback includes `source="native_reopened_project"`, ordered
labels, full matrices, logical cells and combined annotation text, native
binding and mapping, plus the native legend relationship. Verify checks
those scientific fields, editable project existence and PNG/PDF signatures;
Origin additionally checks its required TIF. A mutated native matrix, text
or class color must fail verification even when the confirmed plan is intact.

Example normalized native cell and verify summary (the full reports retain
all 64 cells, values, explicit p-values and palette entries):

```json
{
  "source": "native_reopened_project",
  "point_count": 64,
  "cell": {"row": 0, "column": 1, "row_label": "Demo_1", "column_label": "Demo_2", "r": -0.73, "annotation": "-0.73**"},
  "verify": {"status": "ok", "checks": {"matrix_values": true, "pvalues": true, "annotations": true, "color_mapping": true, "native_binding": true, "linked_color_legend": true}}
}
```

Errors include `invalid_correlation_matrix`, `_shape`, `_symmetry`,
`invalid_correlation_diagonal`, `invalid_correlation_value`,
`invalid_pvalue_matrix`, `invalid_pvalue_range`, `heatmap_unsupported_by_engine`,
`heatmap_render_failed`, `heatmap_readback_failed`, `heatmap_verify_failed`,
`color_mapping_mismatch`, `annotation_mismatch`, and the size guard
`correlation_matrix_too_large`. Verification mismatch codes identify native
color/legend and annotation differences without substituting expected values.

Grapher's `correlation_cells.csv` is the native worksheet backing data and
must stay with the GRF. Keep the complete output directory. The user source
remains read only; SHA-256 is checked before and after render and recorded in
the manifest. No raster plot fallback or fitted/precomputed image is used.

## Performance and limits

Measured wall time includes native activation, creation, exports, save/close,
reopen and scientific readback verification; it is not a bare plotting time.
These are the initial native size probes before the final 8×8 typography and
Origin grid adjustments; their file sizes are probe artifacts, not the final
GUI acceptance files. The final canonical integration was separately rerun.

| Engine | N | Native cells / annotation texts | Seconds | Editable bytes | PNG bytes | PDF bytes | TIF bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Origin | 8 | 64 / 64 | 12.469 | 72,415 | 94,443 | 551,418 | 281,300 |
| Origin | 10 | 100 / 100 | 15.781 | 76,636 | 113,824 | 553,056 | 321,011 |
| Origin | 20 | 400 / 400 | 35.688 | 116,904 | 262,748 | 562,262 | 597,243 |
| Grapher | 8 | 64 / 64 | 25.265 | 311,296 | 159,942 | 1,323,464 | — |
| Grapher | 10 | 100 / 100 | 22.907 | 356,352 | 208,248 | 1,324,270 | — |
| Grapher | 20 | 400 / 400 | 22.171 | 634,880 | 385,354 | 1,330,884 | — |

Each also contains 2N axis-label texts and one title. These figures count
scientific cells and annotation texts, not all graph/axis/worksheet objects.
All six sizes passed scientific save/reopen checks. The recommendation is
N≤10 for annotation readability; 11–20 emits a density warning, and N>20 is
rejected. The 20×20 exported images were visually inspected; labels are dense,
so no broad publication-layout guarantee is made for long names or many stars.
Both Origin and Grapher 8×8 native GUI usability and edit persistence passed
user acceptance. The 10×10 and 20×20 measurements are automated native probes
and exported visual inspection, not separate manual GUI acceptance claims.

## Acceptance ledger

| Gate | Current result |
| --- | --- |
| Core and canonical preview focused tests | PASS: 26 unit + 2 preview tests |
| Canonical Grapher render/reopen/verify, native color/text mutation | PASS: 1 passed |
| Grapher full per-case isolated native regression | PASS: 22/22, zero new leftover PID in every case |
| Origin canonical render/reopen/verify and native matrix/text/color mutation | PASS after final 10 pt typography and white-grid adjustments: 1 passed |
| Final Grapher canonical render/reopen/verify and color/text mutation | PASS: 1 passed |
| Full Origin native regression | PASS: 14 passed, 1067 deselected; known Exit `0x800706be` diagnostics remain |
| Full non-GUI regression | PASS: 1040 passed, 7 skipped, 36 deselected |
| Origin representative GUI / edit / persistence | PASS: final3 artifact, user acceptance on 2026-09-28 |
| Grapher representative GUI / edit / persistence | PASS: final3 artifact, user acceptance on 2026-09-28 |
| Origin post-GUI native verify | PASS: user-saved final3 OPJU reopened, all scientific/export checks true |
| Grapher post-GUI native verify | PASS on isolated retry: user-saved final3 GRF reopened, all scientific/export checks true |
| Version bump / next phase | NOT STARTED; version remains 0.1.0 |

Full regression commands:

```powershell
.test-venv\Scripts\python.exe -m pytest -m "not origin and not grapher" -q
.test-venv\Scripts\python.exe -m pytest -m origin -q --basetemp .phase16-origin-regression
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/test_grapher_isolated.ps1 -OutputDir .phase16-grapher-regression
```

The PowerShell execution-policy option applies only to the local test process;
no system policy was changed. Earlier non-GUI runs are retained as failed:
two stale generated inventories were regenerated; another run had 1038 passed
and one smoke test failure because concurrent real Origin work held the job
lease and added queue-progress messages to a mocked worker. That test passed
alone, then the entire suite passed after the native suite finished. These
earlier failures are not counted as passed runs.

The first post-GUI Grapher verify attempt could not establish one isolated
automation instance and returned a structured failed report before any native
project readback ran. It is **NOT RUN for project verification**, not counted
as a passed check. After confirming zero Grapher processes, a standalone retry
successfully reopened and verified the user-saved GRF. No process was killed,
no fallback was used, and no lifecycle policy was relaxed.

Fixed GUI acceptance artifacts:

- Origin: `.phase16-origin-final3/test_origin_native_correlation0/origin/origin/result.opju`
- Grapher: `.phase16-grapher-final3/test_grapher_native_correlatio0/grapher/grapher/result.grf`

Both contain synthetic data. Origin's ordinary cell text is now 10 pt at
8×8; its normalized scientific readback is unchanged. Stars are not converted
to superscripts or rich-text markup. The exported preview distinguishes
`*`, `**`, `***` without cell annotation overlap. Origin user GUI acceptance
confirmed this; Grapher user acceptance also confirmed editable annotations.

### Origin final representative GUI acceptance — PASS

The user validated the exact `origin-final3` OPJU above. Ordinary 10 pt
annotations distinguish all three significance-star levels without overlap.
White cell separators and the native -1 / 0 / +1 color scale render correctly;
the scale and annotation Text objects remain natively editable. Temporarily
changing a matrix cell from a negative correlation to a positive value changed
the corresponding heatmap color. Restoring the matrix value restored its
color. After restoring the modification, saving, closing and reopening, the
native matrix relationship, annotations, grid and color scale remained intact.
Origin was closed after validation. This proves the native data→color
relationship and is not a raster or decorative fallback.

### Grapher final representative GUI acceptance — PASS

The user validated the exact `grapher-final3` GRF above: the native Class
Scatter object, all 64 cells, ordinary value/star Text objects and the 21-class
legend are editable. Temporarily changing one native class color changed both
the cells in that class and the corresponding native legend swatch. Restoring
the class color restored both. The `correlation_cells.csv` backing data stayed
in place and unchanged. After save → close → reopen, the Class Scatter mapping
and legend relationship remained intact. Grapher was closed after validation.
This proves shared native class mapping, not a decorative or raster fallback.

The final two reopened native verification reports were compared: all 64
correlation values and all 64 supplied p-values are identical after
normalization. Palette modes differ intentionally. Native mutation tests
change the saved project, not the user source or plan: Origin matrix values,
annotations and colormap colors are detected; Grapher annotations and class
colors are detected.

| Capability | Origin 2024 | Grapher 27.1.296 |
| --- | --- | --- |
| Correlation heatmap submode | Implemented; representative GUI PASS | Implemented; representative GUI PASS |
| Native underlying plot | Matrix Heatmap | Class Scatter, type 32 |
| Production scalar color mapping | Native 256 colormap levels | 21 discrete classes |
| Custom continuous mapping | Not claimed as infinitely continuous | Not production-verified |
| Native linked color display | Spectrum scale | Class legend |
| Supplied p-value annotations | Yes | Yes |
| Full generic Heatmap | Existing Origin route unchanged | Unsupported |
| Recommended / hard maximum | 10 / 20 | 10 / 20 |

The 21-class contract is sufficient for honest scientific support when its
quantization, bounds, palette and linked legend are declared. Pixel-identical
continuous color parity is not claimed. Both native GUI gates have now passed:
the bounded correlation-only route is production-ready, and v0.2.0 is
recommended as a separate release decision. No version was changed here.

## Current limitations

- Correlation-only, full matrix; no clustering, arbitrary matrix scaling,
  triangle display, multi-panel or Heatmap AI EditPlan.
- Grapher custom continuous cyan/white/red mapping is not production-verified;
  the supported native contract is 21 explicit intervals with linked legend.
- General Grapher route coverage remains 7/41; this is a documented submode.
- User inspection found ordinary `-0.73**`, Arial, 9 pt with no special
  escape or overbar formatting; the large native Properties preview was
  correct. The requested correction was confined to typography, raising
  8×8 cell text to 10 pt. Thin marks also remain above titles/diagonal values
  in exported previews and occur in Phase 15 outputs. Those observations
  do not establish an Origin markup cause; no scientific semantics were
  changed to address them.
- Existing Origin safe lifecycle policy and Grapher per-job process isolation
  remain unchanged; unknown Origin processes are not force-terminated.
- Version remains 0.1.0. No next phase or release bump is authorized by this
  implementation. Generic Heatmap and custom continuous Grapher mapping remain
  outside this production-ready correlation-only contract.
