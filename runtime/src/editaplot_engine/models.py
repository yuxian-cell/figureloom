"""Small contracts shared by EditaPlot rendering backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class EngineError(RuntimeError):
    def __init__(self, code: str, message: str, *, engine: str | None = None, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.engine = engine
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": "failed",
            "error": {"code": self.code, "message": str(self), **self.details},
        }
        if self.engine:
            payload["engine"] = self.engine
        return payload


class EngineProcessError(EngineError):
    def __init__(self, engine: str, exit_code: int) -> None:
        super().__init__(
            "engine_process_failed",
            f"The {engine} worker exited with code {exit_code}.",
            engine=engine,
            exit_code=exit_code,
        )
        self.exit_code = exit_code


@dataclass(frozen=True)
class RenderResult:
    engine: str
    status: str
    output_dir: Path
    editable_path: Path
    exports: dict[str, Path]
    readback: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "engine": self.engine,
            "output_dir": str(self.output_dir),
            "editable": str(self.editable_path),
            "exports": {name: str(path) for name, path in self.exports.items()},
            "readback": self.readback,
            "metadata": self.metadata,
        }


class Engine(Protocol):
    name: str

    def detect(self) -> dict[str, Any]: ...

    def doctor(self, *, engine_home: str | Path | None = None) -> dict[str, Any]: ...

    def smoke(
        self,
        output_dir: str | Path,
        *,
        engine_home: str | Path | None = None,
        python_executable: str | Path | None = None,
        visible: bool = True,
        keep_application_open: bool = False,
    ) -> dict[str, Any]: ...

    def render(
        self,
        plan: dict[str, Any],
        *,
        plan_file: str | Path,
        engine_home: str | Path | None = None,
        python_executable: str | Path | None = None,
        output_dir: str | Path | None = None,
        close_application: bool = False,
    ) -> RenderResult: ...

    def readback(self, artifact: str | Path) -> dict[str, Any]: ...

    def verify(self, output_dir: str | Path) -> dict[str, Any]: ...

    def apply_edit(self, artifact: str | Path, edit: dict[str, str]) -> dict[str, Any]: ...
