# FigureLoom v0.2.1 — GitHub compatibility hotfix

This release addresses setup and backend selection. It does not add chart routes
or change scientific statistics, error meanings, native renderers or exports.

## Fixes

- `pywin32==312` is a direct Windows runtime dependency in the package metadata,
  formal requirements, locks and Skill environment repair. Fresh installation
  provides `pythoncom`, `win32api` and `win32com.client` for Grapher COM.
- Grapher 27.1.296 is treated as a single-instance application. An already-open
  user application is attached with `ownership=false`; FigureLoom creates its
  own document and never calls Application.Quit for that session. With no open
  application, FigureLoom starts the registered executable, retains the child
  process handle and requests Quit only after verifying ownership and that its
  documents have been closed. Ambiguous ownership is treated conservatively.
  After a successful owned Quit, native references are released and the retained
  child handle is waited on for up to ten seconds before another activation.
  A timeout is reported without killing the process. Heatmap readback records
  documents before opening its GRF and closes only its own backing worksheet;
  a worksheet already open in the user's application is preserved.
- The Agent-facing Skill requires an explicit `origin`, `grapher` or `auto`
  backend choice. Explicit Origin/Grapher requests are hard constraints: doctor,
  chart recommendation and rendering never silently switch apps. `auto` is
  reserved for requests without a backend and currently resolves to Origin.
  The legacy CLI still resolves an omitted `--engine` to Origin.
- Workflow preview, session and runtime logs record `engine_requested`,
  `engine_source`, `engine_resolved` and `fallback_allowed`. Confirmation
  rejects a preview whose frozen backend has changed.
- Standalone source-checkout doctor and verify bootstrap the runtime before
  importing its backend resolver. Origin diagnostics remain available before
  a runtime has been configured.

## Using an existing Grapher window

An Agent request such as “在我已经打开的 Grapher 窗口里绘制” must pass
`--engine grapher` to `workflow-preview`. The rendering task attaches to the
existing application, creates its own graph and preserves the user's documents.
Its GRF is saved, reopened and verified through Grapher native objects. The
user's application stays open when the task finishes.

## Boundaries

- The tested Grapher build does not expose its active application through
  `GetActiveObject`; the runtime falls back to COM activation and verifies the
  existing process identity. An uncertain session is never Quit or killed.
- This repository provides a Codex Skill and CLI, not a bundled Doubao/Claude
  plugin or a natural-language backend parser. Other Agents must use the
  documented three-value backend contract and pass the chosen `--engine`.
- Grapher still requires one disposable Python automation job at a time. Some
  repeated single-process COM operations can conflict. The existing limited
  Grapher route coverage and native weighted-Fit restriction remain unchanged.
- Visual polishing of CO2 plots and new chart families are outside this hotfix.

## Validation

- Fresh Windows CPython 3.12 environment: official constrained editable install,
  direct imports of `pythoncom`, `win32api`, `win32com.client` and the Grapher
  backend, and `pip check` passed. Local testing does not claim fresh installs
  on Python 3.10/3.11; those versions remain covered by Windows CI.
- Non-GUI regression: 1,101 passed, 7 environment skips, 43 native cases deselected.
- Origin native isolated regression: 17/17 passed, including the confirmed-plan
  cross-backend case. Grapher native isolated regression: 26/26 passed, including
  an existing visible window with unsaved user content through smoke, doctor,
  render, save/reopen/readback/verify and native edit. No application process was
  left behind by the final suite.
- Real CO2 group-summary SEM: four native series, independent SEM error bindings,
  GRF/PNG/PDF, reopen/readback/verify and manual GUI editability passed. The original
  plot document and application remained open after automation; the user closed
  the application after accepting the result. The original CSV hash was unchanged.
- Pre-release regression exposed asynchronous owned shutdown and implicit
  heatmap worksheet documents. Both were corrected before the final passing
  runs; earlier failures are retained in local diagnostic logs.
- Public control-surface and backend lint, version consistency, the 441-file
  runtime hash inventory and strict public-source release audit passed. The audit
  checked 768 tracked files with zero errors.

Historical [v0.2.0 release notes](release-v0.2.md) and the existing `v0.2.0`
annotated tag remain unchanged.
