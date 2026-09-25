from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime/src"))
from origin_sciplot.origin_backend import scientific_renderer as renderer  # noqa: E402


class Legend:
    def __init__(self, left: float, top: float) -> None:
        self.values = {"left": left, "top": top, "width": 5.0, "height": 1.0}
        self.attach = None

    def get_float(self, key: str) -> float:
        return self.values[key]

    def set_float(self, key: str, value: float) -> None:
        self.values[key] = value

    def set_int(self, key: str, value: int) -> None:
        assert key == "attach"
        self.attach = value


class Origin:
    def __init__(self) -> None:
        self.refreshed = False

    def lt_float(self, key: str) -> float:
        return {"page.width": 23.5, "page.height": 16.5}[key]

    def lt_exec(self, command: str) -> None:
        assert command == "doc -uw;"
        self.refreshed = True


def test_inherited_legend_outside_page_is_repositioned(monkeypatch) -> None:
    monkeypatch.setattr(
        renderer,
        "read_layer_geometry_percent",
        lambda _op, _layer: {"left_percent": 17.0, "top_percent": 5.5},
    )
    op = Origin()
    legend = Legend(20.0, -0.5)
    renderer._keep_legend_on_page(op, object(), legend)
    assert legend.attach == 1
    assert 0 <= legend.values["left"] <= 23.5 - legend.values["width"]
    assert 0 <= legend.values["top"] <= 16.5 - legend.values["height"]
    assert op.refreshed


def test_existing_in_page_legend_stays_in_place() -> None:
    op = Origin()
    legend = Legend(3.0, 2.0)
    renderer._keep_legend_on_page(op, object(), legend)
    assert legend.values["left"] == 3.0
    assert legend.values["top"] == 2.0
    assert legend.attach is None
    assert not op.refreshed
