"""Thin adapter around the unchanged Origin CLI worker and verifier."""

from __future__ import annotations

import gc
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .fit_contract import FIT_CAPABILITIES, FitSpec, production_linear_fits, selected_weighted_points
from .models import EngineError, EngineProcessError, RenderResult


class OriginEngine:
    name = "origin"

    @staticmethod
    def _core() -> Any:
        import figureloom_core

        return figureloom_core

    @staticmethod
    def _run_worker(
        command: list[str],
        *,
        cwd: Path,
        environment: dict[str, str],
        label: str,
    ) -> dict[str, Any]:
        try:
            process = subprocess.Popen(  # noqa: S603 - command comes from FigureLoom core
                command,
                cwd=str(cwd),
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except PermissionError as exc:
            raise EngineError(
                "worker_start_permission_denied",
                f"Windows blocked the {label} process.",
                engine="origin",
                os_error=type(exc).__name__,
                errno=exc.errno,
            ) from exc
        except OSError as exc:
            raise EngineError(
                "worker_start_failed",
                f"FigureLoom could not start the {label} process.",
                engine="origin",
                os_error=type(exc).__name__,
                errno=exc.errno,
            ) from exc
        if process.stdout is None:
            process.kill()
            raise EngineError("worker_pipe_missing", f"Could not read {label} output.", engine="origin")
        final_payload: dict[str, Any] = {}
        for line in process.stdout:
            text = line.rstrip("\r\n")
            if os.environ.get("FIGURELOOM_HUMAN") != "1":
                print(text, flush=True)
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("type") in {"done", "error"}:
                final_payload = payload
        exit_code = int(process.wait())
        if exit_code:
            raise EngineProcessError("origin", exit_code)
        return final_payload

    def detect(self) -> dict[str, Any]:
        return self._core().discover_origin_application()

    def doctor(self, *, engine_home: str | Path | None = None) -> dict[str, Any]:
        from .correlation_heatmap import HEATMAP_CAPABILITIES

        return {
            "engine": self.name,
            **self._core().doctor(engine_home=engine_home),
            "fit_capabilities": FIT_CAPABILITIES[self.name].to_dict(),
            "heatmap_capabilities": HEATMAP_CAPABILITIES[self.name],
        }

    def smoke(
        self,
        output_dir: str | Path,
        *,
        engine_home: str | Path | None = None,
        python_executable: str | Path | None = None,
        visible: bool = True,
        keep_application_open: bool = False,
    ) -> dict[str, Any]:
        del visible
        core = self._core()
        command, env, root = core.build_origin_smoke_command(
            output_dir=output_dir,
            engine_home=engine_home,
            python_executable=python_executable,
            keep_origin_open=keep_application_open,
        )
        print(
            json.dumps(
                {
                    "type": "figureloom_origin_smoke_start",
                    "engine_home": str(root),
                    "connection_mode": "new_isolated",
                    "output_dir": str(Path(output_dir).expanduser().resolve()),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return self._run_worker(command, cwd=root, environment=env, label="Origin smoke worker")

    def render(
        self,
        plan: dict[str, Any],
        *,
        plan_file: str | Path,
        engine_home: str | Path | None = None,
        python_executable: str | Path | None = None,
        output_dir: str | Path | None = None,
        close_application: bool = False,
    ) -> RenderResult:
        core = self._core()
        if plan.get("correlation_heatmap") is not None:
            from .correlation_runtime import render

            return render(self.name, plan, plan_file, output_dir)
        fit_specs = production_linear_fits(plan)
        fit_spec = fit_specs[0] if len(fit_specs) == 1 else None
        if fit_spec is not None and fit_spec.weight_mode == "column":
            from origin_sciplot.data_loader import load_table

            selected_weighted_points(load_table(plan["source"]["path"]).frame, fit_spec)
        command, env, root = core.build_worker_command(
            plan,
            plan_file=plan_file,
            engine_home=engine_home,
            python_executable=python_executable,
            output_dir=output_dir,
            close_origin=close_application or bool(fit_specs),
        )
        if os.environ.get("FIGURELOOM_HUMAN") != "1":
            print(
                json.dumps(
                    {
                        "type": "figureloom_render_start",
                        "engine": self.name,
                        "engine_home": str(root),
                        "template_id": plan["template"]["id"],
                        "source_sha256": plan["source"]["sha256"],
                        "origin_callability_check": "worker_connection",
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        payload = self._run_worker(command, cwd=root, environment=env, label="Origin render worker")
        editable = Path(str(payload.get("opju", "")))
        if not editable.is_file():
            raise EngineError(
                "origin_render_result_missing",
                "The Origin worker completed without an editable OPJU result.",
                engine=self.name,
            )
        exports = {
            name: Path(str(payload[name]))
            for name in ("png", "pdf", "tif")
            if isinstance(payload.get(name), str)
        }
        fit_readback: dict[str, Any] | None = None
        if fit_specs:
            from origin_sciplot.origin_backend.fit import apply_linear_fit

            fit_readbacks: dict[str, dict[str, Any]] = {}
            entries = []
            for spec in fit_specs:
                error_semantic = (plan["render_spec"]["data"].get("y_errors") or {}).get(spec.y_column)
                error_column = error_semantic["column"] if error_semantic else None
                native = apply_linear_fit(
                    Path(str(payload["output_dir"])), spec, error_column,
                    allow_existing=len(fit_specs) > 1,
                )
                gc.collect()
                fit_readbacks[spec.y_column] = native
                entries.append({"spec": spec.to_dict(), "error_column": error_column, "readback": native})
            fit_readback = next(iter(fit_readbacks.values())) if len(fit_specs) == 1 else None
            fit_manifest = {
                "engine": "origin",
                "engine_version": entries[-1]["readback"]["engine_version"],
                "result_source": "backend_native",
                **({"spec": entries[0]["spec"], "error_column": entries[0]["error_column"],
                    "readback": entries[0]["readback"]} if fit_spec else {"fits": entries}),
            }
            (Path(str(payload["output_dir"])) / "fit-manifest.json").write_text(
                json.dumps(fit_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            verify_path = Path(str(payload["output_dir"])) / "origin_verify_report.json"
            verify_report = json.loads(verify_path.read_text(encoding="utf-8"))
            verify_report["fit" if fit_spec else "fits"] = (
                fit_readback if fit_spec else fit_readbacks
            )
            verify_path.write_text(json.dumps(verify_report, ensure_ascii=False, indent=2), encoding="utf-8")
            verified = self.verify(Path(str(payload["output_dir"])))
            if verified["status"] != "ok":
                raise EngineError("fit_verify_failed", "Origin Fit verification failed", engine=self.name)
        result = RenderResult(
            engine=self.name,
            status="ok",
            output_dir=Path(str(payload["output_dir"])),
            editable_path=editable,
            exports=exports,
            readback={"fit": fit_readback} if fit_spec else {"fits": fit_readbacks} if fit_specs else {},
            metadata={
                "engine_version": payload.get("origin_version"),
                "editable_format": "opju",
                "verify_report": payload.get("origin_verify_report"),
                **({"fit": fit_readback["result"]} if fit_spec else {}),
                **({"fits": {name: native["result"] for name, native in fit_readbacks.items()}}
                   if len(fit_specs) > 1 else {}),
            },
        )
        (result.output_dir / "render-result.json").write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result

    def readback(self, artifact: str | Path) -> dict[str, Any]:
        from .correlation_runtime import is_correlation_project, readback

        if is_correlation_project(Path(artifact)):
            return readback(self.name, Path(artifact).resolve())
        report = Path(artifact).resolve().parent / "origin_verify_report.json"
        if not report.is_file():
            raise EngineError(
                "origin_readback_missing", "Origin readback report is missing.", engine=self.name
            )
        return json.loads(report.read_text(encoding="utf-8"))

    def apply_edit(self, artifact: str | Path, edit: dict[str, str]) -> dict[str, Any]:
        """Edit the saved OPJU through an owned Origin instance, then reopen it."""
        if edit["operation"] != "set_axis_title":
            raise EngineError(
                "edit_unsupported", "Origin supports axis-title edits in this workflow.", engine=self.name
            )
        path = Path(artifact).resolve()
        if not path.is_file():
            raise EngineError("artifact_not_found", "The native OPJU is missing.", engine=self.name)
        from origin_sciplot.origin_backend.export_utils import export_graph
        from origin_sciplot.origin_backend.fit import _main_graph
        from origin_sciplot.origin_backend.session import OriginSession

        with OriginSession(keep_open=False) as session:
            op = session.op
            if not op.open(str(path), asksave=False):
                raise EngineError("edit_open_failed", "Origin could not open the OPJU.", engine=self.name)
            graph = _main_graph(op)
            if graph is None:
                raise EngineError("edit_target_not_found", "No native graph exists.", engine=self.name)
            plot_count = len(graph[0].plot_list())
            graph[0].axis(edit["axis"]).title = edit["value"]
            if not op.save(str(path)):
                raise EngineError("edit_save_failed", "Origin could not save the OPJU.", engine=self.name)
            export_graph(
                op, graph, path.with_suffix(".png"), path.with_suffix(".pdf"), path.with_suffix(".tif")
            )
            op.new(asksave=False)
            if not op.open(str(path), asksave=False):
                raise EngineError("edit_readback_failed", "Edited OPJU cannot reopen.", engine=self.name)
            graph = _main_graph(op)
            actual = graph[0].axis(edit["axis"]).title if graph is not None else None
            reopened_count = len(graph[0].plot_list()) if graph is not None else 0
        del graph, op, session
        gc.collect()
        if actual != edit["value"] or reopened_count != plot_count:
            raise EngineError("edit_verify_failed", "Origin axis title did not persist.", engine=self.name)
        return {"status": "ok", "engine": self.name, "operation": edit["operation"],
                "actual": actual, "plot_count": reopened_count,
                "verification": "native_reopen_readback"}

    def verify(self, output_dir: str | Path) -> dict[str, Any]:
        from .correlation_runtime import is_correlation_project, verify

        if is_correlation_project(Path(output_dir) / "result.opju"):
            return verify(self.name, Path(output_dir).resolve())
        result = self._core().verify_output(output_dir)
        report = {
            "status": "ok" if result["programmatic_pass"] else "failed",
            "engine": self.name,
            "editable_format": "opju",
            **result,
        }
        fit_manifest_path = Path(output_dir) / "fit-manifest.json"
        plan_copy = Path(output_dir) / "render-plan.json"
        plan: dict[str, Any] = {}
        planned_fit = None
        if plan_copy.is_file():
            plan = json.loads(plan_copy.read_text(encoding="utf-8"))
            planned_fit = plan.get("fit")
        if planned_fit is not None and not fit_manifest_path.is_file():
            report["status"] = "failed"
            report["ok"] = report["programmatic_pass"] = False
            report["checks"] = {"native_fit": False, "artifact_reopened": False}
            report["error"] = {"code": "native_fit_relationship_lost", "message": "Fit manifest is missing"}
            return report
        if fit_manifest_path.is_file():
            from origin_sciplot.origin_backend.fit import verify_linear_fit

            try:
                fit_manifest = json.loads(fit_manifest_path.read_text(encoding="utf-8"))
                if "fits" in fit_manifest:
                    entries = fit_manifest["fits"]
                    if planned_fit != [entry["spec"] for entry in entries]:
                        raise EngineError(
                            "fit_verify_failed", "Saved independent FitSpecs differ from RenderPlan",
                            engine=self.name,
                        )
                    native_fits = {}
                    report_refs = set()
                    curve_refs = set()
                    for entry in entries:
                        spec = FitSpec.from_dict(entry["spec"])
                        saved_fit = entry["readback"]
                        native = verify_linear_fit(
                            Path(output_dir), spec, saved_fit["report_sheet"], saved_fit["curve_sheet"],
                            multi_series=True,
                        )
                        gc.collect()
                        if not all((
                            native["present"], native["curve_present"], native["scatter_present"],
                            native["source_x_column"] == spec.x_column,
                            native["source_y_column"] == spec.y_column,
                            native["result"]["result_source"] == "backend_native",
                            native["result"]["weight_mode"] == "none",
                            native["full_range"],
                        )):
                            raise EngineError(
                                "fit_verify_failed", "Independent Origin Fit lost native binding",
                                engine=self.name,
                            )
                        native_fits[spec.y_column] = native
                        report_refs.add(native["report_sheet"])
                        curve_refs.add(native["curve_sheet"])
                    if (
                        len(native_fits) != len(entries)
                        or len(report_refs) != len(entries)
                        or len(curve_refs) != len(entries)
                    ):
                        raise EngineError(
                            "fit_verify_failed", "Independent Origin Fits share native analysis objects",
                            engine=self.name,
                        )
                    report["checks"] = {"native_fit": True, "artifact_reopened": True}
                    report["readback"] = {"fits": native_fits}
                    report["ok"] = report["programmatic_pass"]
                    report["status"] = "ok" if report["ok"] else "failed"
                    (Path(output_dir) / "origin_fit_verify_report.json").write_text(
                        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    return report
                spec = FitSpec.from_dict(fit_manifest["spec"])
                if FitSpec.from_dict(planned_fit) != spec:
                    raise EngineError(
                        "fit_verify_failed", "Saved FitSpec differs from RenderPlan", engine=self.name
                    )
                saved = fit_manifest["readback"]
                expected_error = (
                    (plan["render_spec"]["data"].get("y_errors") or {})
                    .get(spec.y_column, {})
                    .get("column")
                )
                if fit_manifest.get("error_column") != expected_error:
                    raise EngineError(
                        "fit_verify_failed", "Error binding differs from RenderPlan", engine=self.name
                    )
                native = verify_linear_fit(
                    Path(output_dir), spec, saved["report_sheet"], saved["curve_sheet"],
                    expected_error, saved.get("fit_source_ref"),
                )
                gc.collect()
                error_ok = expected_error is None or (
                    native["error"]["present"] is True
                    and native["error"]["column"] == expected_error
                    and native["error"]["direction"] == "y"
                    and native["error"]["symmetric"] is True
                )
                range_ok = (
                    native["full_range"] is (spec.fit_range is None)
                    and tuple(native["result"]["fit_range"] or ()) == tuple(spec.fit_range or ())
                )
                if not range_ok:
                    raise EngineError(
                        "fit_range_mismatch", "Saved Origin Fit does not use the requested X interval",
                        engine=self.name,
                    )
                weight_ok = (
                    native["result"]["weight_mode"] == spec.weight_mode
                    and native["result"].get("weight_column") == spec.weight_column
                    and native["result"].get("weight_interpretation") == spec.weight_interpretation
                    and (spec.weight_mode == "none" or (
                        f'"{spec.weight_column}"' in (native.get("source_weight_binding") or "")
                        and native.get("weighting_readback") == "direct_weight_verified"
                    ))
                )
                if not weight_ok:
                    raise EngineError(
                        "weight_verify_mismatch", "Saved Origin Fit lost direct weight binding",
                        engine=self.name,
                    )
                fit_ok = all(
                    (
                        native["present"], native["curve_present"], native["scatter_present"],
                        native["result"]["model"] == spec.model,
                        native["result"].get("degree") == spec.degree,
                        native.get("native_degree") == spec.degree,
                        spec.model == "linear" or native.get("operation_binding") is not None,
                        native["result"]["result_source"] == "backend_native",
                        native["source_x_column"] == spec.x_column,
                        native["source_y_column"] == spec.y_column,
                        native["scatter_n_points"] == plan.get("source", {}).get("row_count"),
                        weight_ok,
                        error_ok,
                    )
                )
                report["checks"] = {
                    "native_fit": fit_ok, "artifact_reopened": True,
                    **({"native_error": error_ok} if expected_error else {}),
                }
                report["readback"] = {"fit": native}
            except (EngineError, KeyError, ValueError, OSError) as exc:
                fit_ok = False
                report["checks"] = {
                    "native_fit": False, "artifact_reopened": False,
                    **(
                        {"native_error": False}
                        if plan.get("render_spec", {}).get("data", {}).get("y_errors") else {}
                    ),
                }
                report["error"] = {
                    "code": getattr(exc, "code", "fit_verify_failed"), "message": str(exc)
                }
            report["ok"] = report["programmatic_pass"] = report["programmatic_pass"] and fit_ok
            report["status"] = "ok" if report["ok"] else "failed"
            (Path(output_dir) / "origin_fit_verify_report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return report


__all__ = ["OriginEngine"]
