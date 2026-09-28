"""Native Grapher symmetric Y error bars for existing XY plots."""

from typing import Any

from figureloom_engine.models import EngineError

from .smoke import get, put

# Grapher 27 Type Library: grfReadFromData=1, grfBoth=0, grfNone=0.
_READ_FROM_DATA = 1
_BOTH = 0
_NONE = 0


def add_y_error(plot: Any, column_index: int, *, color: int | None = None) -> None:
    try:
        bars = get(plot, "ErrorBars")
        put(bars, "HorzBarType", _NONE)
        put(bars, "VertCustomNegativeBar", False)
        put(bars, "VertBarCol", column_index)
        put(bars, "VertBarDirection", _BOTH)
        put(bars, "VertBarType", _READ_FROM_DATA)
        if color is not None:
            put(get(bars, "line"), "foreColor", color)
            put(get(bars, "VertLine"), "foreColor", color)
    except Exception as exc:
        raise EngineError("grapher_errorbar_create_failed", str(exc), engine="grapher") from exc


def read_y_error(plot: Any) -> dict[str, Any]:
    try:
        bars = get(plot, "ErrorBars")
        vertical_type = int(get(bars, "VertBarType"))
        if vertical_type == _NONE:
            return {"present": False}
        column_index = int(get(bars, "VertBarCol"))
        if (
            vertical_type != _READ_FROM_DATA
            or column_index < 1
            or int(get(bars, "VertBarDirection")) != _BOTH
            or bool(get(bars, "VertCustomNegativeBar"))
            or int(get(bars, "HorzBarType")) != _NONE
        ):
            raise ValueError("Grapher error bars are not symmetric Y errors read from a column.")
        return {
            "present": True,
            "column_index": column_index,
            "direction": "y",
            "symmetric": True,
            "line_color": int(get(get(bars, "line"), "foreColor")),
            "cap_color": int(get(get(bars, "VertLine"), "foreColor")),
        }
    except Exception as exc:
        raise EngineError("grapher_errorbar_readback_failed", str(exc), engine="grapher") from exc
