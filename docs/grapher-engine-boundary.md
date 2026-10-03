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


## Grapher 27.1.296 attach-or-own investigation (2026-09-29)

A local desktop probe confirmed that `Dispatch` and `DispatchEx` reuse the same running
Grapher PID and document collection. Releasing the COM reference preserves a desktop-launched
window. `GetActiveObject` returned `MK_E_UNAVAILABLE` both before and after desktop startup;
it is tried first, but this version needs activation as the attach fallback. Activating during
startup can fail transiently, or briefly create another automation process. The official
[Application documentation](https://grapherhelp.goldensoftware.com/auto_objects/LINK_AppObject.htm)
describes CreateObject as activating a new instance; that is not proof of a new process on this build.

Production render/readback/edit/verify, correlation heatmaps, live doctor, smoke and fit probes
share `grapher_sciplot.smoke.application`. Existing windows have `ownership=false`: no visibility
changes and no Quit. For the no-window path we explicitly launch the registered executable with
`/Automation`, retain its child handle, wait for input idle plus a short COM readiness delay,
and validate the live child, sole PID, executable path, hidden state and empty document collection.
Only this verified child has `ownership=true`. Cleanup requests Quit only if its identity remains
verified and its document collection is empty. Ambiguous activation/cleanup is reported and
released without terminating any process. No process-name kill or PID-difference ownership claim
is used. Each Python job should still be disposable: this does not remove the previously documented
limitations of repeatedly restarting Grapher COM in one long-lived Python process.

Opening an already-open GRF is refused before acquiring it, so cleanup cannot close an existing
user document. Save/reopen/native readback and staging-file verification are unchanged.
Ownership, connection mode and PID are recorded in smoke, doctor and render metadata.

The v0.2.1 follow-up puts the owned shutdown boundary at each application lease:
release caller-held native references, request Quit, release the session reference,
then wait up to ten seconds on the retained child handle. A timeout is a structured
cleanup error; it never triggers a process kill. This prevents the next readback
activation from treating a still-exiting automation child as a user's session.
Correlation readback snapshots documents before GRF Open, because opening a native
graph can also open its backing worksheet. Only the task's worksheet is closed;
a worksheet present in that snapshot is retained. The adjacent CSV is never deleted
or modified by readback.

`pywin32==312` is a direct runtime dependency, pinned in all release/runtime/Skill dependency copies.
A fresh virtual environment must import `pythoncom`, `win32api`, `win32com.client` and
`grapher_sciplot.engine` without relying on Origin or development tools to install pywin32.

Run `pytest -m "not origin and not grapher"` for mocked lifecycle and dependency-contract checks.
`tools/test_grapher_isolated.ps1` runs each native case in a disposable Python process, including
an owned-session smoke and a harness-launched desktop window containing unsaved user content.
The desktop case exercises smoke, doctor, render, reopen/verify and edit, and checks that the
original PID, visible window, document count and unsaved text survive. Its cleanup only requests
Quit for the process explicitly launched by that test; when a user window exists it only closes
the test's own sentinel document and preserves that window.

Validation for this fix: a clean Windows CPython 3.12 virtual environment installed the runtime
under the official constraints, passed `pip check`, and directly imported all three pywin32
modules and the Grapher backend. Non-GUI regression: 1,077 passed, 7 environment skips.
Grapher native regression: 26/26 passed with no newly observed process left behind; the existing
window and unsaved document case also passed. The no-window native smoke recorded
`ownership=true`, exported GRF/PNG/PDF, reopened and read back the native graph, and exited.
The strict public-release dependency audit and lint checks passed. Windows CI retains Python
3.10/3.11/3.12 coverage and now explicitly checks pywin32 imports; local fresh-install testing
here used 3.12, without claiming local execution on the other two Python versions.
