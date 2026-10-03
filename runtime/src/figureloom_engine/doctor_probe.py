"""One-shot native activation probe, run in a disposable Python process."""

from __future__ import annotations

import json
import sys


def probe(engine: str) -> dict[str, object]:
    if engine == "origin":
        from origin_sciplot.origin_backend.session import OriginSession

        with OriginSession(keep_open=False) as session:
            return {"engine": engine, "version": session.environment.origin_version,
                    "automation": "ok", "shutdown_requested": True}
    if engine == "grapher":
        from grapher_sciplot.engine import _application

        with _application(visible=False) as (_app, info):
            try:
                return {"engine": engine, "version": info["version"],
                        "automation": "ok", "shutdown_requested": info["ownership"],
                        "ownership": info["ownership"], "connection_mode": info["connection_mode"],
                        "pid": info["pid"]}
            finally:
                _app = None
    raise ValueError(f"Unknown engine: {engine}")


if __name__ == "__main__":
    try:
        result = probe(sys.argv[1])
    except Exception as exc:
        result = {"engine": sys.argv[1], "automation": "failed",
                  "error": {"code": getattr(exc, "code", f"{sys.argv[1]}_unavailable"),
                            "message": str(exc)}}
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["automation"] == "ok" else 2)
