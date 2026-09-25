"""Lazy engine registry; importing it never activates a desktop application."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .models import Engine, EngineError

DEFAULT_ENGINE = "origin"
_ENGINE_TYPES = {
    "origin": ("editaplot_engine.origin", "OriginEngine"),
    "grapher": ("grapher_sciplot.engine", "GrapherEngine"),
}


def available_engines() -> tuple[str, ...]:
    return tuple(_ENGINE_TYPES)


def get_engine(name: str | None = None) -> Engine:
    selected = (name or DEFAULT_ENGINE).strip().casefold()
    try:
        module_name, class_name = _ENGINE_TYPES[selected]
    except KeyError as exc:
        raise EngineError(
            "unknown_engine",
            f"Unknown rendering engine: {selected}",
            engine=selected,
            available_engines=list(available_engines()),
        ) from exc
    engine_type: Any = getattr(import_module(module_name), class_name)
    return engine_type()
