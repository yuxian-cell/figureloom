"""Lazy engine registry; importing it never activates a desktop application."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .models import Engine, EngineError

DEFAULT_ENGINE = "origin"
_ENGINE_TYPES = {
    "origin": ("figureloom_engine.origin", "OriginEngine"),
    "grapher": ("grapher_sciplot.engine", "GrapherEngine"),
}


def available_engines() -> tuple[str, ...]:
    return tuple(_ENGINE_TYPES)


def resolve_engine_request(name: str | None = None) -> dict[str, Any]:
    """Freeze the backend before plot recommendation; explicit requests never fall back."""
    requested = ("auto" if name is None else name.strip().casefold())
    resolved = DEFAULT_ENGINE if requested == "auto" else requested
    if resolved not in _ENGINE_TYPES:
        raise EngineError(
            "unknown_engine", f"Unknown rendering engine: {requested}",
            engine=requested, available_engines=list(available_engines()),
        )
    return {
        "engine_requested": requested,
        "engine_source": "unspecified" if requested == "auto" else "explicit_user_request",
        "engine_resolved": resolved,
        "fallback_allowed": requested == "auto",
    }


def get_engine(name: str | None = None) -> Engine:
    selected = resolve_engine_request(name)["engine_resolved"]
    module_name, class_name = _ENGINE_TYPES[selected]
    engine_type: Any = getattr(import_module(module_name), class_name)
    return engine_type()
