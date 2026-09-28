# FigureLoom v0.1 release gate

Status: **v0.1 release-ready (0.1.0)** under the explicitly accepted conservative Origin cleanup policy. Native tests, fresh-environment Quickstart and representative GUI acceptance are complete. Prior failures remain recorded below.

- [x] Git working tree clean after release commit (verified by the final release command)
- [x] Runtime and CLI version 0.1.0
- [x] Origin/Grapher live doctor checked (Origin shutdown warns about unknown residual process)
- [x] Non-GUI full regression — final frozen-code run: 1012 passed, 7 skipped, 34 deselected
- [x] Origin native regression — final rerun 13/13 passed; `0x800706be` exit diagnostics remain
- [x] Grapher native regression, one case per process — 21/21, zero new PIDs after each job
- [x] CSV→Grapher and XLSX→Origin render/edit E2E passed in separate CLI calls
- [x] Representative GUI: Grapher native line/edit, Origin error plot/axis edit, Fit relationship
- [x] Repeated isolated lifecycle acceptance — Grapher 21 clean jobs; Origin user window preserved across doctor and real smoke
- [x] Quickstart commands exercised in a newly created Python 3.12 virtual environment
- [x] Source hashes unchanged after both workflows
- [x] Session resume across CLI processes
- [x] Bad-path regression complete — missing source/sheet/column, unsupported weighting, unavailable backends, missing artifacts, invalid edit/target and unwritable output covered by the passing non-GUI suite
- [x] Known limitations documented
- [x] Release notes ready

## Observed Phase 15 results so far

Grapher live doctor: automation `ok`, version `27.1.296`, `clean_shutdown`. Origin live doctor: automation `ok`, version `10.10` (OriginPro 2024); immediate shutdown check reported `unknown_process_remaining`, and a later process check found no Origin process. No unknown PID was killed. A separate automation-owned Origin instance survived FigureLoom attach/detach and isolated work. Manual user-opened Origin protection subsequently passed with PID 21372, as detailed below.

The first full non-GUI run returned **3 failed, 1004 passed, 7 skipped, 34 deselected** because the runtime manifest and route inventory had not yet been regenerated and new CSV examples were inside the curated public asset tree. Examples were moved to `docs/quickstart-data`, both generated records were refreshed, and those three previously failing checks passed. A later full run returned **1009 passed, 7 skipped, 34 deselected**. One additional bad-path test was added. A concurrent non-GUI run had a smoke-worker output assertion fail because the Origin native suite held the Origin job slot and emitted queue-progress events; the isolated test passed. The final non-GUI rerun with no competing Origin job returned **1010 passed, 7 skipped, 34 deselected**.

The first isolated Grapher run returned 18/21 because three route tests asserted process disappearance before their own Python process exited. All 21 jobs had zero new PID at the accepted job boundary. The tests were aligned with that boundary; the final full isolated rerun returned **21/21 passed**, zero new PID per job. The earlier 18/21 run is not counted as a pass.

Representative GUI acceptance: the user opened the Phase 15 Origin OPJU and confirmed both native error-bar series, the edited `Current (mA)` Y title and editable Plot Details. The user then opened the Phase 15 Grapher multi-line GRF and confirmed Control solid, Treatment dashed, editable native lines and legend. A separate native Linear Fit GRF remained editable and recalculated. All requested GUI checks passed; Grapher was closed afterward.

The Phase 15 Origin native suite returned **13 passed, 1037 deselected** in 11m27s. It printed `0x800706be` from `originpro.exit()` during multi-Fit and polynomial teardown; these diagnostics remain a runtime limitation, not an Origin render/readback failure. Three `Origin64.exe -Embedding` processes were visible afterward, with no reliable per-job ownership identity, so none was terminated. A fresh-environment live doctor reported the three preexisting processes and `unknown_process_remaining`. The next XLSX→Origin render/edit workflow completed and left the same three PIDs, demonstrating recovery with preexisting unknown processes. The independent automation-owned Origin surrogate survived attach/detach and isolated work. A user-opened Origin project window with PID 21372 remained intact, including its project title, after an isolated live doctor and a full `origin-smoke` passed with OPJU/PNG/PDF/TIF. This is the manual user-owned protection acceptance.

The final Origin rerun returned **13 passed, 1038 deselected** in 11m29s after the logging and workflow status hardening. `0x800706be` teardown diagnostics recurred; three unknown `Origin64.exe -Embedding` PIDs were visible afterward. No process was terminated by FigureLoom. Native correctness and the next-job recovery check remain green, while cleanup ownership remains a documented limitation.

Phase 14's 21 Grapher native cases must run with `tools/test_grapher_isolated.ps1`; a shared COM process is not an accepted substitute. Origin lifecycle identity still cannot be proven through the installed COM interface; the safe policy is `Exit`, release references, log/warn, and never kill a process by name or a PID difference.

## Frozen-code release gate — 2026-09-28

All 21 final Grapher case logs in `.phase15-grapher-release-gate` contain `1 passed`. The runner reached case 21, so its stop-on-leftover guard did not fire for earlier cases; the final process snapshot contained no Grapher or Origin process. The earlier complete observed run independently reported zero new PID for each of 21 jobs. No native process was terminated.

Final non-GUI run: **1012 passed, 7 skipped, 34 deselected in 101.56s**, exit 0, with no competing native test job. Modified Python files pass Ruff; `git diff --check` passes. The generated runtime manifest and route inventory checks pass within the full suite. Source hashes for both new-environment Quickstart workflows stayed unchanged; sessions resumed across separate CLI processes.

Release decision: **release-ready** for the Windows Python/CLI v0.1 scope. No new route, Fit model, EditPlan operation, installer or later phase was started. Origin exit diagnostics/unknown process ownership, Grapher isolated execution and unsupported explicit weighted Fit remain limitations, not hidden success claims.
# Phase 17 development gate

Correlation Heatmap adaptive native layout passed Concrete 9-variable matrix,
supplied p-values and raw-data Pearson native tests. All four representative
Origin/Grapher projects passed user GUI acceptance; the final Origin Whole Page
viewport patch also passed automatic tests and user reopen spot-check. Phase 17
is approved for commit, with version remaining 0.1.0. No v0.2.0 bump,
tag or release is authorized. See [Phase 17 evidence](correlation-heatmap-phase17.md).
