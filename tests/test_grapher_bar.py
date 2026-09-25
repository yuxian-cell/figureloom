from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "runtime/src", ROOT / "skill/editaplot/scripts"):
    sys.path.insert(0, str(path))

import editaplot_core as core  # noqa: E402
from editaplot_engine.models import EngineError  # noqa: E402
from grapher_sciplot.engine import GrapherEngine, _plot_mode  # noqa: E402

FIXTURES = ROOT / "tests/fixtures/grapher_bar"


def bar_plan(name: str) -> dict:
    source = FIXTURES / f"{name}.csv"
    columns = source.read_text(encoding="utf-8").splitlines()[0].split(",")
    mapping = {
        "assignments": {
            column: "category" if column == "Group" else "error" if column.endswith("_SD") else "series"
            for column in columns
        }
    }
    proposal = core.understand_data(source, template_id="bar", mapping=mapping, engine_home=ROOT / "runtime")
    return core.build_plan(
        source,
        template_id="bar",
        claim="Response differs across groups.",
        evidence_role="comparison",
        mapping=mapping,
        semantic_confirmation=proposal["confirmation_gate"]["confirmation_payload_template"],
        engine_home=ROOT / "runtime",
    )


@pytest.mark.parametrize(
    ("name", "chart_type", "y", "errors"),
    [
        ("simple", "simple_bar", ["Control"], {}),
        ("grouped", "grouped_bar", ["Control", "Treatment"], {}),
        ("simple_error", "simple_bar", ["Control"], {"Control": "Control_SD"}),
        (
            "grouped_error",
            "grouped_bar",
            ["Control", "Treatment"],
            {"Control": "Control_SD", "Treatment": "Treatment_SD"},
        ),
    ],
)
def test_bar_render_plan_semantics(name: str, chart_type: str, y: list[str], errors: dict[str, str]) -> None:
    plan = bar_plan(name)
    spec = plan["render_spec"]
    assert spec["chart_type"] == chart_type
    assert spec["data"]["category"] == "Group"
    assert spec["data"]["y"] == y
    assert {column: value["column"] for column, value in spec["data"].get("y_errors", {}).items()} == errors
    _, staged = GrapherEngine._prepare(plan)
    assert list(staged.columns) == ["Group", *y, *errors.values()]
    assert staged["Group"].tolist() == ["A", "B", "C", "D"]


@pytest.mark.parametrize(
    ("contents", "code"),
    [
        ("Wrong,Control\nA,10\n", "invalid_category"),
        ("Group,Control\nA,bad\n", "value_column_not_numeric"),
        ("Group,Control,Control_SD\nA,10,bad\n", "error_column_not_numeric"),
        ("Group,Control\n,10\n", "invalid_category"),
    ],
)
def test_bar_rejects_invalid_staging(tmp_path: Path, contents: str, code: str) -> None:
    plan = bar_plan("simple_error" if "Control_SD" in contents else "simple")
    source = tmp_path / "invalid.csv"
    source.write_text(contents, encoding="utf-8")
    plan["source"]["path"] = str(source)
    with pytest.raises(EngineError) as raised:
        GrapherEngine._prepare(plan)
    assert raised.value.code == code


def test_scatter_mode_requires_native_invisible_line() -> None:
    assert _plot_mode(1, "Invisible") == "xy_scatter"
    assert _plot_mode(1, "Solid") == "xy_line"
