# Engine boundary and Grapher backend

## Runtime flow

```text
inspect → recommend → understand → semantic confirmation → RenderPlan 1.4
    → Engine registry (default: origin)
        ├── OriginEngine → existing origin_sciplot worker → OPJU + PNG/PDF/TIF
        └── GrapherEngine → native Grapher COM objects → GRF + PNG/PDF
```

The Engine boundary is after `validate_plan` and before backend application launch. Analysis,
scientific semantics, confirmation, palette choice, source identity, and output policy remain shared.

## Code ownership

| Shared | Origin | Grapher |
| --- | --- | --- |
| `figureloom_core.py`, RenderPlan, `figureloom_engine/models.py`, registry and CLI dispatch | `OriginEngine` adapts the unchanged `origin_sciplot` worker and verifier | `grapher_sciplot/engine.py` owns COM launch, native XY creation, GRF save, export, reopen, readback and verify |

`grapher_sciplot` does not import `origin_sciplot`. The first formal Grapher route reads the frozen
backend-neutral `render_spec` and creates a deterministic staging CSV from the original CSV/XLSX.

## Engine contract

```python
class Engine(Protocol):
    name: str
    def detect(self) -> dict: ...
    def doctor(self, *, engine_home=None) -> dict: ...
    def smoke(self, output_dir, **options) -> dict: ...
    def render(self, plan, *, plan_file, output_dir=None, **options) -> RenderResult: ...
    def readback(self, artifact) -> dict: ...
    def verify(self, output_dir) -> dict: ...
```

`RenderResult` exposes `engine`, `status`, `editable`, `exports`, neutral readback, and metadata.
Unknown engines fail with `unknown_engine` and list `origin` and `grapher`.

## RenderPlan compatibility

RenderPlan 1.4 adds:

- `render_spec`: chart type, source column bindings, axis titles, basic style and dimensions;
- `backend_options.origin`: capability profile, optional capabilities, lifecycle hint and outputs;
- `backend_options.grapher`: required Grapher outputs.

Origin-only fields were removed from `template` and `execution`. Version 1.3 plans remain accepted
by the Origin adapter. The existing Origin worker, templates, graph construction and export code were
not changed.

## CLI

```powershell
figureloom doctor --engine grapher
figureloom smoke --engine grapher --output-dir <directory>
figureloom render render-plan.json --engine grapher
figureloom verify <output-directory> --engine grapher
```

Omitting `--engine` selects Origin. `origin-smoke` and `grapher-smoke` remain compatibility aliases.
`--engine-home` still locates the runtime and does not select a backend.

## Phase 2 Grapher support

The Grapher backend supports confirmed `scatter` → `xy_scatter` (one X, one Y) and `trend` →
`xy_line` (one X, one or more Y columns). Both routes use the same document, staging CSV, native graph,
axis, save/export, readback, and verification path. Verification checks nonempty native GRF/PNG/PDF,
successful GRF reopen, staged data identity, each plot's native worksheet/column binding and visual
mode, axis and graph titles, colors, and multi-series legend labels. Other routes return
`grapher_route_unsupported`. See [XY Line acceptance](grapher-xy-line.md).
