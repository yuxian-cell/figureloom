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
| `editaplot_core.py`, RenderPlan, `editaplot_engine/models.py`, registry and CLI dispatch | `OriginEngine` adapts the unchanged `origin_sciplot` worker and verifier | `grapher_sciplot/engine.py` owns COM launch, native XY creation, GRF save, export, reopen, readback and verify |

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
editaplot doctor --engine grapher
editaplot smoke --engine grapher --output-dir <directory>
editaplot render render-plan.json --engine grapher
editaplot verify <output-directory> --engine grapher
```

Omitting `--engine` selects Origin. `origin-smoke` and `grapher-smoke` remain compatibility aliases.
`--engine-home` still locates the runtime and does not select a backend.

## Phase 2 Grapher support

The formal route supports one confirmed `xy_scatter` with exactly one X and one Y column. It maps
the graph title, axis titles, symbol color/size and output dimensions. Verification requires nonempty
native GRF/PNG/PDF signatures, successful GRF reopen, one XY scatter binding to staging columns 1/2,
and matching X/Y titles. Other Grapher chart routes return `grapher_route_unsupported`.
