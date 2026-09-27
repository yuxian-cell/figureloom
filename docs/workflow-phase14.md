# Phase 14 — current workflow audit

Status: audit before production changes. Phase 13 Batch 1 was committed separately as `21e7c41`.

## Actual path today

```text
CLI inspect/start/recommend (source CSV/TXT/XLS/XLSX)
  → origin_sciplot.data_loader.load_table + structured inspect_data profile
  → TemplateServiceRegistry preparation + deterministic recommend_charts scores
  → CLI understand --template-id (structured semantic proposal and proposal hash)
  → explicit semantic-confirmation JSON
  → CLI plan / build_plan (one source-bound, backend-neutral RenderPlan)
  → CLI render --engine origin|grapher
  → OriginEngine worker or GrapherEngine COM
  → editable OPJU/GRF and native exports
  → CLI verify and backend readback
```

These are separate commands. A person currently carries the recommendation's template ID and confirmation payload into the later commands. `start_session` is a read-only beginner proposal, not a persisted render/edit session. `recommend_charts` is deterministic and structured, but ranks the verified Origin route catalog without filtering for the selected backend. Grapher rejects unsupported routes in `_prepare` and rejects explicit weighted Linear Fit before native execution. RenderPlan remains the shared scientific contract.

## Existing contracts to reuse

| Stage | Existing production code | Current limit |
| --- | --- | --- |
| Input and profile | `load_table`, `inspect_data` | CSV and XLSX are read-only; XLSX chooses the first nonempty worksheet and exposes its sheet name, but callers cannot select a worksheet. |
| Recommendation | `recommend_charts`, `TemplateServiceRegistry` | Structured scores and reason codes; not engine aware. |
| Confirmation | `understand_data`, proposal hash and `build_plan` confirmation gate | Explicit and source-bound; user must pass JSON manually. |
| Plan | `build_plan`, `validate_plan` | One canonical RenderPlan, source hash, column mapping and plot semantics. |
| Engine | `get_engine`, `OriginEngine`, `GrapherEngine` | Origin default; engine-specific validation partly happens inside `render`. |
| Artifacts | `RenderResult`, per-engine manifests and verify reports | No common resumable session manifest or edit history. |
| Readback | Grapher native GRF object readback; Origin worker verify report and native Fit analysis readback | Origin's generic `OriginEngine.readback` loads a prior report, so a new edit path must reopen and inspect the actual OPJU. |
| Native editing | Manual Origin/Grapher GUI only | No allowlisted EditPlan, CLI edit command, or second invocation that changes an existing native project. |

## Required glue and feasibility gates

1. Build one user-facing workflow entry that calls the existing inspect/recommend/understand/build-plan/engine methods, with explicit confirmation before native rendering. Keep existing low-level commands unchanged.
2. Add selected-sheet handling for ordinary XLSX tables without changing the default first-nonempty-sheet behavior.
3. Record a session JSON containing source hash, selected sheet, recommendation/confirmation, RenderPlan path/hash, engine, exact artifact paths, readback and verification. Resume from disk, not Python memory.
4. Use a small backend-neutral allowlist for native edits. Before implementing the edit loop, prove both applications can reopen an owned project, change a named native object, save, reopen and read that value. If either cannot, stop rather than reconstructing a fake image or rewriting Core.
5. Keep Grapher jobs on one owned automation lifecycle each. Investigate Origin `-Embedding` processes by ownership; do not terminate a process whose ownership is unclear.

The first representative edit should be a Y-axis title, which is present in the existing RenderPlan and both native object models. A named series line-style edit and native Fit-range edit require separate probes before they can be advertised. No new renderer family or scientific capability is needed for the workflow contract itself.

## Verification targets

Real-file E2E tests must start at CSV/XLSX ingest, create a confirmation-bound RenderPlan, then render, reopen, read back and verify the native artifact. A second process must load the session and edit that same artifact. A Grapher weighted-fit request must return `unsupported_fit_weighting` without creating a successful session. Existing Origin and Grapher direct RenderPlan APIs remain supported.

## Implemented Phase 14 path

```text
workflow-preview <source> --engine origin|grapher [--sheet NAME] [--template-id ID]
  → read-only source fingerprint; XLSX sheet discovery/selection
  → existing inspect_data + recommend_charts (Grapher route candidates filtered)
  → existing understand_data and source-bound confirmation proposal
  → workflow-preview.json
workflow-render workflow-preview.json --claim TEXT --confirm
  → existing build_plan and one canonical render-plan.json
  → engine doctor → existing native render → existing verify → session.json
edit session.json "把 Treatment 改成虚线"
  → allowlisted EditPlan → reopen existing GRF → change named native plot
  → save/export → close/reopen/readback → verify → append session history
edit session.json "把 Y 轴标题改成 Current (mA)"
  → reopen existing OPJU → change native axis → save/export
  → close/reopen/readback, preserve native plot count → append history
```

The preview requires a second explicit command with `--confirm`; neither recommendation nor a preview alone renders. Existing `inspect`, `recommend`, `understand`, `plan`, `render`, and `verify` remain callable. A selected XLSX worksheet is materialized as a deterministic CSV **inside the run workspace** because the existing template service accepts a path and chooses the first nonempty sheet. The original XLSX stays read-only and its path, SHA-256, selected sheet and available sheet names remain in the session; the RenderPlan's effective source is the selected-sheet staging CSV. This is a workflow adapter, not a change to scientific column semantics.

The existing route recommender remains engine-neutral. The workflow filters candidate routes to those currently supported by Grapher, then lets an explicit template override win. For generic numeric `X + two Y` data where Scatter and Trend scores are within 0.05, it selects Trend so both Y series remain visible. A specified Fit is not subject to that tie rule. The preview still exposes the candidate scores and role candidates for review.

### Persisted contracts

| File | Key fields |
| --- | --- |
| `workflow-preview.json` | original source identity, effective source identity, DatasetProfile with columns/roles/missing counts/candidates, recommendation candidates and selected template, structured understanding, fit/mapping intent, engine |
| `render-plan.json` | existing canonical scientific plan, proposal hash confirmation, source/column mapping and plan hash |
| `session.json` | run ID, timestamps, source identities, recommendation, confirmation, plan path/hash, engine, exact editable/export artifact paths, current readback, verification and append-only edit history |
| EditPlan | allowlisted `set_axis_title` (`x`/`y`, nonempty value) or `set_line_style` (named series, `solid`/`dashed`). The CLI accepts either a narrowly parsed phrase or `--edit-json`; raw COM/LabTalk is never accepted. |

Origin and Grapher both support `set_axis_title` in the workflow. Grapher also supports `set_line_style` for a named line series: `dashed` maps to Grapher's installed `.1 in. Dash` native style. Origin's named-series line-style edit is deliberately unsupported because its saved native value did not survive the probe. Fit-range modification is also not advertised as an EditPlan operation yet; the existing native partial-range **render** capability remains intact. A failed or unsupported edit does not append successful history.

The `session.json` can be loaded by a later CLI process. If the native project is missing, edit returns `artifact_not_found`; if the original source hash changed, it returns `source_changed_since_render` and asks for explicit rerender. The source is never modified. Export files are refreshed by the native application after an edit. Grapher updates its expected axis title manifest before running its existing native verify; Origin performs a fresh OPJU reopen and native axis/plot-count readback for edit verification.

### Real-file evidence so far

| Scenario | Result |
| --- | --- |
| CSV `X,Control,Treatment` → Grapher | GRF/PNG/PDF created; edit in a second CLI process changed only Treatment to `.1 in. Dash`, while Control remained `Solid`; native readback and verify passed. |
| XLSX selected `Data` sheet with Control/Treatment SD → Origin | OPJU/PNG/PDF/TIF created; edit in a second CLI process changed Y title to `Current (mA)`; OPJU save/reopen/readback passed. First attempt failed to save because the old Origin keep-open default held the file; workflow now passes `close_application=True`, and the fresh rerun passed. |
| Same multi-series RenderPlan → both engines | Grapher and Origin generated their own native projects from the identical plan; both retained ordered Control/Treatment mappings. |
| Grapher + explicit direct-weight Fit | `unsupported_fit_weighting` before native rendering; no successful session or GRF. |
| Minimal Linear Fit JSON → Grapher and Origin | Workflow normalizes it through existing `FitSpec`; both created native Fit projects from real CSV. A later axis-title edit preserved the Grapher Fit's native statistics and the Origin Fit's native reopen/verify relationship. Fit-range editing was not performed. |

The baseline Grapher single-process COM conflict still requires one owned lifecycle per job; the workflow CLI uses separate processes for render and edit and `DispatchEx` for each Grapher job. `OriginSession` uses `NEW_ISOLATED` and calls `op.exit()` for its owned instance. Earlier tests produced transient `Origin64.exe -Embedding` processes; ownership across exited workers cannot be proven from the process list, so no broad process termination is performed. `origin_owned_process_cleanup_unresolved` remains a runtime limitation for Phase 15.

Known visual debt remains Origin's crowded automatic Fit statistics box. No new renderer, route family or plotting capability was added. Representative native GUI acceptance and final full regression counts are recorded below when completed.

## GUI and final regression

Representative GUI review **PASS**: CSV Grapher multi-series GRF retained separate editable native Control/Treatment objects, with Control solid and Treatment dashed; XLSX Origin error OPJU retained both native error sources (including Control → `Control_SD`), Y title `Current (mA)` and editable Plot Details; edited Grapher Fit GRF retained a native editable/recalculable Linear Fit and the `Response` Y title after save/reopen. Grapher and Origin were closed after review. An earlier Grapher GUI launch displayed its licensing dialog; automatic review disallowed clicking `Continue Trial`, so that launch was not counted as a GUI pass. Automated results are:

| Suite | Result |
| --- | --- |
| Full non-GUI | 1000 passed, 7 skipped, 34 native tests deselected after FitSpec normalization and structured input-error checks |
| Full Origin native | Final rerun 13 passed, 1028 deselected, including XLSX edit and same-plan dual-engine cases; exit code 0 with `originpro.exit()` COM `0x800706be` teardown diagnostics |
| Full Grapher native, each case in its own Python process | Final rerun 21/21 passed, including CSV edit E2E; each case ended with zero new Grapher PIDs. An earlier rerun stopped at case 2 during concurrent GUI review with a COM activation/resource error and a transient Grapher process; it was not counted as passed. The clean rerun after GUI closure passed. A separate native Fit workflow probe passed after FitSpec normalization. |
| Lint and diff | Ruff and `git diff --check` passed |

No Grapher process remained after the final isolated suite. Three `Origin64.exe -Embedding` processes started during the final Origin suite and remained visible after its successful exit; earlier Origin processes were no longer present. There is no reliable per-job ownership handle for those post-exit processes, so none was terminated. The Origin lifecycle issue is recorded as `origin_owned_process_cleanup_unresolved`, not as a scientific render or test failure.
