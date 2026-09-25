# Grapher category Bar phase 5

## Engine boundary

`ScientificPlotSpec` and RenderPlan carry `category_column`, ordered `series`, and each series' existing `error_column`/`error_kind`. `render_spec.data.category`, `data.y`, and optional `data.y_errors` are the engine-neutral contract. Origin keeps its own helper X offsets and column-plot logic; Grapher uses native category Bar objects. No aggregation is performed by the Grapher renderer.

## Native API evidence

The installed Grapher 27 Type Library exposes `IAutoShapes.AddBarChartGraph`, `IAutoGraph.AddBarChart`, `IAutoBarChart` (`xCol`, `yCol`, `Stacked`, `Orientation`, `Fill`, `line`, `ErrorBars`), and `IAutoAxisTickLabels` (`Mode`, `WorksheetDataCol`, `WorksheetLabelCol`, `FirstLabelRow`). An isolated COM probe created two bars with separate native error columns, saved a GRF, reopened it, and read both plots and axes. This matches [Grapher's AutoBarChart documentation](https://grapherhelp.goldensoftware.com/auto_objects/LINK_AutoBarChart.htm) and [category Bar documentation](https://grapherhelp.goldensoftware.com/Graphs/Category_Bar_Charts.htm). Script Recorder was not needed.

The native vertical category plot uses `SetPlotType(31)`, `xCol=0` (Sequence), and worksheet-backed X tick labels from the original text category column. The first label row is 2 because the staged CSV has a header. Multi-series bars use `GroupsAdjacent=True`, `Stacked=False`, and the RenderPlan series order. `AutoBarChart.ErrorBars` accepts the same symmetric Y error-column binding as XY plots. Both `ErrorBars.line.foreColor` and `VertLine.foreColor` are set from the series palette and checked after reopening.

The old Scatter line came from `line.width=0`: Grapher draws it one pixel wide. `SetPlotType(28)` selects native Scatter and persists `line.style=Invisible`; readback and verification now check that state. Origin's clipped top text was an inherited legend with page coordinates outside the export page. The existing renderer relocates only overflowing legends inside the layer and verifies legend geometry before export.

## Real artifacts and checks

The retained `.phase5-e2e` directory contains `simple_bar`, `grouped_bar`, `bar_error`, and `grouped_bar_error` as GRF/PNG/PDF, plus each render's staging CSV and JSON verification report. Every Grapher GRF reopened, reported one graph and two axes, retained ordered Y bindings, native worksheet category labels, palette colors, and its expected per-series errors. Scatter regression output has symbols and no connecting line. Origin `line_error` single and multi outputs both produced OPJU/PNG/PDF/TIF with in-page legends.

Tests: 10 real Grapher integration cases passed; the full non-Grapher/Origin GUI suite passed with 959 passed, 7 skipped, 11 deselected. A full native GUI edit check is separately requested from the user.

The same simple Bar RenderPlan reached Origin's existing renderer, but that route failed its color readback (`get -c` returned 1 for a column plot; expected the planned palette color). This occurs in the existing Origin Bar styling/verification path before the new legend placement code. A one-line color-order experiment did not fix it and was reverted. Origin Bar dual-backend parity is therefore **not verified**; its color setter/readback needs a separate native Origin investigation. No claim is made that all Origin Bar outputs passed.

## Fit architecture for the next phase

Fit semantics (model family, data subset, weights, parameters, uncertainty, and provenance) belong in the shared analysis contract. Each engine can create an editable native fit object where its capabilities and readback are verified. A common numerical reference calculation would make coefficients comparable, while native objects would preserve manual editing. The next phase should first compare Origin and Grapher fitting APIs and decide which tool owns the authoritative numerical result; no Fit route is implemented here.
