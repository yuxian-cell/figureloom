"""Thin adapter around the unchanged Origin CLI worker and verifier."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

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
        command, env, root = core.build_worker_command(
            plan,
            plan_file=plan_file,
            engine_home=engine_home,
            python_executable=python_executable,
            output_dir=output_dir,
            close_origin=close_application,
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
        result = RenderResult(
            engine=self.name,
            status="ok",
            output_dir=Path(str(payload["output_dir"])),
            editable_path=editable,
            exports=exports,
            metadata={
                "engine_version": payload.get("origin_version"),
                "editable_format": "opju",
                "verify_report": payload.get("origin_verify_report"),
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
        return {
            "status": "ok" if result["programmatic_pass"] else "failed",
            "engine": self.name,
            "editable_format": "opju",
            **result,
        }


__all__ = ["OriginEngine"]
