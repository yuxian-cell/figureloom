# Phase 15A — Origin automation lifecycle investigation

Status: conservative v0.1 policy accepted after real native suites, next-job recovery and manual user-window protection. No process termination policy has been added.

## Current creation and cleanup path

`OriginEngine.render` starts an EditaPlot worker subprocess. Its renderer uses
`OriginSession(connection_mode=NEW_ISOLATED)`; the first `originpro.set_show(False)`
call lazily creates `OriginExt.Application()`. The wrapper's `APP.Exit()` calls
`Application.Exit(releaseonly=False)` and clears its own `_app` reference.
`ATTACH_EXISTING` instead uses `OriginExt.ApplicationSI()` and `Detach()`;
`OriginSession.__exit__` never calls `exit()` for a user-owned attached session.
The Phase 14 workflow requests `close_application=True`, and Fit helpers use
`keep_open=False`. Edit also uses a fresh `OriginSession(keep_open=False)`.

The installed `OriginExt.Application` API exposes `Exit` but no documented
process ID or main-window handle member. Its Python type has no `PID`, `HWND`,
`GetWindowHandle`, or similar property. A PID appearing after an automation
call is therefore not by itself proof that it belongs to that COM object;
concurrent user launch is possible. The safe baseline remains `op.exit()` on
the job's own wrapper and **no process-name or `-Embedding` kill**.

OriginLab's [OriginExt external-Python instructions](https://docs.originlab.com/externalpython/originext/)
show `Application()`, `Exit()`, and deletion of the Python application reference
to ensure closure. Origin C has a documented
[`GetWindow(OGW_MAIN)`](https://docs.originlab.com/originc/ref/getwindow/)
function, but there is no confirmed path yet from this project's external COM
object to that handle. Until one is demonstrated, HWND-to-PID cleanup is not
implemented.

## Existing evidence

Phase 14's final Origin native suite exited 0 with 13 passed, but printed
`0x800706be` from `originpro.config.APP.Exit → OriginExt.Application.Exit`
during Fit teardown. Three `Origin64.exe -Embedding` processes started during
that suite and were still visible afterward. Their post-exit job identity was
not established, so none was terminated. At the start of this Phase 15 audit,
the Origin process list was empty.

Two independent real probes then started with zero Origin processes:

| Probe | After create | After `Exit` and a 3-second wait | After Python reference release/GC |
| --- | --- | --- | --- |
| Direct `OriginExt.Application` | One new `Origin64.exe -Embedding` | Same process still present | Process gone |
| `OriginSession(keep_open=False)` | One new `Origin64.exe -Embedding`; ownership recorded as `editaplot` | Same process still present; `originpro.po._app` is already `None` | Process gone after `gc.collect()`, even while `op` and session variables remain |

Holding a worksheet page proxy did not prevent shutdown after the application
reference was released and GC ran. A third OriginSession probe showed that GC
alone (while `op` and session variables remained) was sufficient. This
supports a best-effort `gc.collect()` after owned `op.exit()`; it does **not**
prove that every Fit teardown `0x800706be` or every residual process has the
same cause. A later `OriginSession` probe created a blank workbook, saved an
OPJU, and closed the project: the same PID was present after save, project
close, and exit request, then disappeared after GC outside the `with` block.
The collection inside `OriginSession.__exit__` alone did not make the process
disappear at that point, so it is not claimed as a complete cleanup fix.
A separate-owner probe held one external Origin process (PID 18208) while
EditaPlot attached/detached through `ApplicationSI`, then ran a new isolated
Origin session. The external process survived both operations. Its owner then
exited normally; the final process set was empty. This is an automation-owned
surrogate for a user-opened window, not a manual GUI acceptance. A unit test
also ensures `ATTACH_EXISTING` calls `detach()` and never `exit()`.

`0x800706be` was observed in the earlier Fit suite during `op.exit()`, not
during source ingestion, save, or readback. The direct and blank-project probes
above did not reproduce it. Thus the exact Fit teardown trigger remains open.

## Safe v0.1 policy

`OriginSession` still calls `Exit` only for its own `Application()` instance and
`Detach` for `ApplicationSI()` attached sessions. It now makes a best-effort
Python GC pass after owned exit; the Fit adapter also releases returned COM
proxies at its outer call boundary. No Origin process is killed by name, launch
argument, or before/after PID difference. A new instance cannot currently be
mapped to a reliable HWND/PID through the installed external COM interface.
Unknown residual processes therefore remain a documented runtime limitation,
not an automatic termination target.

## Grapher comparison

Grapher uses `DispatchEx("Grapher.Application")` for each automation job and
never calls `GetActiveObject`. The prior cleanup path called COM `Quit`, then
force-terminated a PID inferred solely from a process-list difference. That
last step was removed: a concurrent user launch makes the difference
insufficient ownership proof. The runtime now requests COM `Quit` and leaves
process-exit verification to the isolated job boundary. A real smoke test
passed after this change and left no Grapher process when its Python job ended.
If COM `Quit` itself fails, the cleanup warning is preserved without replacing
the primary render/edit error. The final Phase 15 release gate will repeat
multiple isolated jobs and check post-job PID differences.

## Next decision

If the COM object can yield a verifiable PID/HWND identity, use it only for
owned-instance observability and safe cleanup. Otherwise keep the conservative
policy: exit and release the owned COM wrapper, collect unreachable Python COM
proxies, warn about unknown residual processes, and do not terminate them.

## Phase 15 live doctor and workflow evidence

The doctor now has an optional `--live` probe in a short-lived Python process. On this host Grapher 27.1.296 returned `automation=ok` and `shutdown=clean_shutdown`. OriginPro 2024 returned `automation=ok`, version 10.10, then `shutdown=unknown_process_remaining` on the immediate post-child snapshot. One `Origin64.exe -Embedding` PID remained at that point; it was not terminated. After the subsequent CSV/Grapher and XLSX/Origin Quickstart workflows, a process snapshot showed no Origin or Grapher process. The PID-difference warning is a diagnostic, **not** an ownership claim.

`session.json` is written via temporary file, flush, fsync and replace. A workflow enters `rendering` or `editing` before native work; interrupted work is recognized as `incomplete_session`. A failed native render, readback, verify or edit records a failed state. Native cleanup errors do not replace a primary edit/render error. `runtime.log` records run ID, engine and stage; `--verbose` adds the native exception chain, including COM details, without logging table contents.

The full Phase 15 Origin native suite passed 13/13. It still printed `0x800706be` during native Fit teardown. Three `Origin64.exe -Embedding` processes were visible afterward and remained untouched. A fresh Python environment then passed a live Origin doctor and a complete XLSX→Origin render/edit while those processes existed; the doctor called out the preexisting count and its own immediate shutdown warning. After the new workflow, the same three PIDs remained and no additional Origin process was visible. This supports the documented recovery policy but does not establish ownership of the three PIDs or resolve the COM exit diagnostic.

The user then opened the Phase 15 Origin OPJU in the GUI and confirmed native error bars, the edited Y-axis title and editable Plot Details. Its window PID was 21372. While that window stayed open, EditaPlot ran a new isolated live doctor followed by a real `origin-smoke` that saved and verified OPJU/PNG/PDF/TIF. PID 21372 and its project title remained unchanged after both jobs. The three prior unknown processes also remained; none was killed. This is the manual user-owned instance protection acceptance.

A final full Origin native rerun passed 13/13 in 11m29s. `0x800706be` appeared again during Fit teardown, and three unknown `Origin64.exe -Embedding` PIDs remained visible afterward. There is still no reliable mapping from the COM object to those PIDs; the conservative no-kill policy remains in force.

## Final release snapshot — 2026-09-28

The final frozen-code Grapher isolated run wrote 21 passing case logs in `.phase15-grapher-release-gate`. The runner reached case 21 (it stops on a newly remaining PID), and the final process snapshot contained neither Grapher nor Origin. The earlier fully observed 21-case run also reported zero new PID after every job. This later empty snapshot does not erase the Origin exit diagnostics or establish ownership of earlier residual processes.
