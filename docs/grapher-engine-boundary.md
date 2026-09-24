# Grapher backend: phase 1 boundary and smoke

## Current flow

```text
editaplot.cmd → bootstrap_editaplot.py → editaplot.py / editaplot_core.py
    → inspect → recommend → understand → semantic confirmation → RenderPlan 1.3
    → build_worker_command → origin_sciplot.workers.run_template_worker
    → runtime/templates/<id>/runner.py → origin_sciplot.origin_backend
    → Origin → OPJU + PNG/PDF/TIF + Origin object readback
```

`--engine-home` and `EDITAPLOT_ENGINE_HOME` locate the *runtime directory*. They do not select a drawing application. The runtime marker currently requires `origin_sciplot` and its worker.

## Boundary

| Mostly software independent, though currently under `origin_sciplot` | Origin specific |
| --- | --- |
| `data_loader`, `scientific_workflow`, `semantic_analysis`, `semantic_contract`, `template_service`, `palette_catalog`, reference parsing/style, source hash and confirmation in `editaplot_core.py` | `origin_backend/`, `workers/origin_smoke_worker.py`, `workers/run_template_worker.py`, template `runner.py` files, OPJU/export/readback/verify code |

The insertion point is **after `validate_plan` and before `build_worker_command` launches an Origin worker**. `RenderPlan` 1.3 is not fully engine neutral: `template.origin_capability_profile`, `execution.keep_origin_open`, `origin_callability_check`, `required_outputs`, and the default target text encode Origin. The plan freezes a digest and `worker_mapping`, but does not serialize the full scientific `plot_spec`; the worker re-prepares it from the source. A Grapher renderer must perform the same source-hash, semantic-confirmation, mapping, and digest checks before translating the prepared plot specification into native Grapher objects.

## Phase 1 result

`editaplot.cmd grapher-smoke [--output-dir <parent>] [--hidden]` creates a unique subdirectory with `smoke.csv`, native `smoke.grf`, Grapher-exported PNG/PDF, and `smoke-report.json`. It starts an isolated `Grapher.Application`, closes the document, reopens the GRF, and reads graph/plot/axis counts plus X/Y column assignments from the COM Object Model. The smoke does not use `RenderPlan` or change any Origin runner.

The installed Grapher 27.1.296 type library lists the required methods, but several live COM DISPIDs differ from its generated Python wrapper. The PoC resolves method names against the live `IDispatch` for each call. It refuses to quit an application unless COM activation creates one new Grapher process.

## Smallest next interface

```python
class Engine:
    def detect(self) -> dict: ...
    def smoke(self, output_dir) -> dict: ...
    def render(self, confirmed_plan, output_dir) -> dict: ...
    def verify(self, output_dir) -> dict: ...
```

`render` owns launch, editable save, export, readback, and cleanup. Separate public methods for each step would expose application lifecycle details before any caller needs them. `OriginEngine` can delegate to the existing worker and `verify_output` without changing Origin rendering. `GrapherEngine` should initially accept one confirmed XY route and return a structured unsupported-template error for other routes. Add `--engine` with default `origin`; retain `--engine-home` for runtime discovery. An unknown engine should fail before COM activation. Keep old Origin plans valid and their output policy unchanged; introduce engine-specific plan fields/version only when Grapher render is ready.

Likely touch points for phase 2: `skill/editaplot/scripts/editaplot.py`, `editaplot_core.py`, `runtime/src/grapher_sciplot/`, a small runtime Engine selector, and tests. Leave `runtime/src/origin_sciplot/origin_backend/` and existing `runtime/templates/*/runner.py` unchanged.
