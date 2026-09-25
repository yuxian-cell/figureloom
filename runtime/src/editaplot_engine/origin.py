"""Thin adapter around the unchanged Origin CLI worker and verifier."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .fit_contract import FitSpec, production_linear_fit
from .models import EngineError, EngineProcessError, RenderResult


class OriginEngine:
    name = "origin"

    @staticmethod
    def _core() -> Any:
        import editaplot_core

        return editaplot_core

    @staticmethod
    def _run_worker(
        command: list[str],
        *,
        cwd: Path,
        environment: dict[str, str],
        label: str,
    ) -> dict[str, Any]:
        try:
            process = subprocess.Popen(  # noqa: S603 - command comes from EditaPlot core
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
                f"EditaPlot could not start the {label} process.",
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
        return {"engine": self.name, **self._core().doctor(engine_home=engine_home)}

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
                    "type": "editaplot_origin_smoke_start",
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
        fit_spec = production_linear_fit(plan)
        command, env, root = core.build_worker_command(
            plan,
            plan_file=plan_file,
            engine_home=engine_home,
            python_executable=python_executable,
            output_dir=output_dir,
            close_origin=close_application or fit_spec is not None,
        )
        print(
            json.dumps(
                {
                    "type": "editaplot_render_start",
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
        if fit_spec is not None:
            from origin_sciplot.origin_backend.fit import apply_linear_fit

            error_semantic = (plan["render_spec"]["data"].get("y_errors") or {}).get(
                fit_spec.y_column
            )
            error_column = error_semantic["column"] if error_semantic else None
            fit_readback = apply_linear_fit(Path(str(payload["output_dir"])), fit_spec, error_column)
            fit_manifest = {
                "engine": "origin",
                "engine_version": fit_readback["engine_version"],
                "result_source": "backend_native",
                "spec": fit_spec.to_dict(),
                "error_column": error_column,
                "readback": fit_readback,
            }
            (Path(str(payload["output_dir"])) / "fit-manifest.json").write_text(
                json.dumps(fit_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            verify_path = Path(str(payload["output_dir"])) / "origin_verify_report.json"
            verify_report = json.loads(verify_path.read_text(encoding="utf-8"))
            verify_report["fit"] = fit_readback
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
            readback={"fit": fit_readback} if fit_readback else {},
            metadata={
                "engine_version": payload.get("origin_version"),
                "editable_format": "opju",
                "verify_report": payload.get("origin_verify_report"),
                **({"fit": fit_readback["result"]} if fit_readback else {}),
            },
        )
        (result.output_dir / "render-result.json").write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result

    def readback(self, artifact: str | Path) -> dict[str, Any]:
        report = Path(artifact).resolve().parent / "origin_verify_report.json"
        if not report.is_file():
            raise EngineError(
                "origin_readback_missing", "Origin readback report is missing.", engine=self.name
            )
        return json.loads(report.read_text(encoding="utf-8"))

    def verify(self, output_dir: str | Path) -> dict[str, Any]:
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
                    Path(output_dir), spec, saved["report_sheet"], saved["curve_sheet"], expected_error
                )
                error_ok = expected_error is None or (
                    native["error"]["present"] is True
                    and native["error"]["column"] == expected_error
                    and native["error"]["direction"] == "y"
                    and native["error"]["symmetric"] is True
                )
                fit_ok = all(
                    (
                        native["present"], native["curve_present"], native["scatter_present"],
                        native["full_range"], native["result"]["result_source"] == "backend_native",
                        native["source_x_column"] == spec.x_column,
                        native["source_y_column"] == spec.y_column,
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
