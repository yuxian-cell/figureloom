# Grapher XY Line acceptance

The symmetric Y error proposal below was implemented in [Phase 4](grapher-error-bar-phase4.md)
with `direction: "y"` and `symmetric: true` as separate neutral fields.

`trend` plans freeze `render_spec.chart_type = "xy_line"`; `scatter` remains `xy_scatter`.
The only Core change is this neutral chart type and a neutral line width in points. Origin rendering
continues to consume its existing plot specification. Grapher uses one XY render path for both modes:
source read → deterministic staging CSV → document/graph → one native line plot per Y column → axes
and title → GRF/PNG/PDF → reopen/readback → verify. No separate `xy_common.py` is needed yet.

The installed Grapher 27 type library and a real save/reopen probe confirmed `graph.AddLinePlot`,
`graph.AddLegend(True)`, `plot.Name`, `legend.EntryName`, and line/symbol properties. Scatter sets
symbol frequency to 1 and line width to 0. Line sets positive width and defaults to no symbols.
The legend for multiple Y columns uses the source column names. Fixed fallback colors preserve
series order when no palette is specified; two renders of the same plan returned the same native
line color values. Grapher's graph title must be unlinked from its object name before setting text.

## Acceptance evidence

- Native single-line and two-line GRF, PNG, PDF are retained under `.phase3-e2e/` with the source,
  inspect, understand, RenderPlan, staging CSV, manifest, and verification reports.
- Both GRFs reopened through Grapher COM. Readback confirmed plot count 1/2, X column 1, Y columns
  2/3, positive line width, no default symbols, matching axis titles, graph title, and
  `Control`/`Treatment` legend entries for the two-line graph.
- The old phase-two scatter GRF reopened and verified with the new readback. It remained
  symbol-only, with line width 0.
- Default-engine Origin rerender generated OPJU/PNG/PDF/TIF and passed the established Origin
  object readback and verifier. Manual inspection of the exported PNG found all five scatter
  points visible at (1,1), (2,4), (3,9), (4,16), (5,25), correctly labelled X/Y axes, readable
  ticks and markers, no clipped text, and no unnecessary legend. The OPJU was checked by Origin's
  existing object readback; no Origin renderer files were changed. Direct GUI inspection of the OPJU
  remains pending: the Computer Use window capture returned `0x80004002` twice. The empty Origin
  instance opened for that attempt was closed without opening or changing a project.

## Next stage: symmetric Y error

Core already records `ScientificSeries.error_column` and `error_kind`. The smallest neutral
RenderPlan addition is a per-series mapping alongside `data.y`, for example:

```json
{
  "data": {
    "x": "Time",
    "y": ["Control"],
    "y_errors": {
      "Control": {
        "direction": "symmetric",
        "column": "Control_SD",
        "kind": "sd"
      }
    }
  }
}
```

`kind` should retain the confirmed source meaning (`sd`, `sem`, `ci`, or `custom`); an explicit
error column is never silently calculated from replicates. A later asymmetric form can use
`negative_column` and `positive_column` under the same Y key. Origin and Grapher object properties
remain in their adapters. This is a design proposal; no error-bar renderer is added in this stage.
