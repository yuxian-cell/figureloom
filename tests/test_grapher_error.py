from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "skill/editaplot/scripts", ROOT / "runtime/src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import editaplot_core as core  # noqa: E402
from editaplot_engine.models import EngineError  # noqa: E402
from grapher_sciplot import error_bar  # noqa: E402
from grapher_sciplot.engine import GrapherEngine  # noqa: E402
from origin_sciplot.scientific_workflow import ScientificWorkflowError, _pair_errors  # noqa: E402

FIXTURES = ROOT / "tests/fixtures/grapher_error"


def test_unmatched_multi_series_errors_do_not_bind_by_column_order() -> None:
    with pytest.raises(ScientificWorkflowError) as raised:
        _pair_errors(["Control", "Treatment"], ["FirstError", "SecondError"])
    assert raised.value.code == "error_pair_ambiguous"


def _plan(source: Path, template: str, columns: tuple[str, ...]) -> dict:
    mapping = {
        "assignments": {
            column: ("x" if column == "Time" else "error" if column.endswith("_SD") else "series")
            for column in columns
        }
    }
    proposal = core.understand_data(
        source, template_id=template, mapping=mapping, engine_home=ROOT / "runtime"
    )
    return core.build_plan(
        source,
        template_id=template,
        claim="Values increase with time.",
        evidence_role="trend",
        mapping=mapping,
        semantic_confirmation=proposal["confirmation_gate"]["confirmation_payload_template"],
        engine_home=ROOT / "runtime",
    )


@pytest.mark.parametrize(
    ("name", "columns", "expected"),
    [
        ("line_single.csv", ("Time", "Control", "Control_SD"), {"Control": "Control_SD"}),
        (
            "line_multi.csv",
            ("Time", "Control", "Control_SD", "Treatment", "Treatment_SD"),
            {"Control": "Control_SD", "Treatment": "Treatment_SD"},
        ),
    ],
)
def test_confirmed_error_plan_binds_each_series(
    name: str, columns: tuple[str, ...], expected: dict[str, str]
) -> None:
    plan = _plan(FIXTURES / name, "line_error", columns)
    errors = plan["render_spec"]["data"]["y_errors"]
    assert {y: item["column"] for y, item in errors.items()} == expected
    assert {item["kind"] for item in errors.values()} == {"sd"}
    assert all(item["direction"] == "y" and item["symmetric"] for item in errors.values())
    assert list(GrapherEngine._prepare(plan)[1].columns) == ["Time", *expected, *expected.values()]


@pytest.mark.parametrize(
    ("suffix", "kind"), [("SEM", "sem"), ("SE", "sem"), ("CI", "ci"), ("ERR", "explicit")]
)
def test_error_kind_is_semantic_label_for_explicit_column(tmp_path: Path, suffix: str, kind: str) -> None:
    column = f"Control_{suffix}"
    source = tmp_path / "kind.csv"
    source.write_text(f"Time,Control,{column}\n0,10,1\n1,14,2\n", encoding="utf-8")
    mapping = {"assignments": {"Time": "x", "Control": "series", column: "error"}}
    proposal = core.understand_data(
        source, template_id="line_error", mapping=mapping, engine_home=ROOT / "runtime"
    )
    plan = core.build_plan(
        source,
        template_id="line_error",
        claim="Trend.",
        evidence_role="trend",
        mapping=mapping,
        semantic_confirmation=proposal["confirmation_gate"]["confirmation_payload_template"],
        engine_home=ROOT / "runtime",
    )
    assert plan["render_spec"]["data"]["y_errors"]["Control"]["kind"] == kind


def test_scatter_error_uses_same_series_contract_and_no_error_remains_optional() -> None:
    with_error = _plan(FIXTURES / "line_single.csv", "scatter", ("Time", "Control", "Control_SD"))
    assert with_error["render_spec"]["chart_type"] == "xy_scatter"
    assert with_error["render_spec"]["data"]["y_errors"]["Control"]["column"] == "Control_SD"
    without = _plan(FIXTURES / "no_error.csv", "trend", ("Time", "Control"))
    assert "y_errors" not in without["render_spec"]["data"]


def test_invalid_error_columns_and_shapes_have_structured_codes(tmp_path: Path) -> None:
    plan = _plan(FIXTURES / "line_single.csv", "line_error", ("Time", "Control", "Control_SD"))
    cases = (
        (FIXTURES / "missing_error.csv", "missing_error_column"),
        (tmp_path / "text.csv", "error_column_not_numeric"),
        (tmp_path / "short.csv", "error_length_mismatch"),
    )
    cases[1][0].write_text("Time,Control,Control_SD\n0,10,bad\n1,14,2\n", encoding="utf-8")
    cases[2][0].write_text("Time,Control,Control_SD\n0,10,1\n1,14,\n", encoding="utf-8")
    for source, code in cases:
        altered = {**plan, "source": {**plan["source"], "path": str(source)}}
        with pytest.raises(EngineError) as raised:
            GrapherEngine._prepare(altered)
        assert raised.value.code == code
    error = plan["render_spec"]["data"]["y_errors"]["Control"]
    for changes, code in (
        ({"direction": "x"}, "unsupported_error_direction"),
        ({"symmetric": False}, "unsupported_asymmetric_error"),
        ({"negative_column": "Lower"}, "unsupported_asymmetric_error"),
    ):
        altered = {
            **plan,
            "render_spec": {
                **plan["render_spec"],
                "data": {**plan["render_spec"]["data"], "y_errors": {"Control": {**error, **changes}}},
            },
        }
        with pytest.raises(EngineError) as raised:
            GrapherEngine._prepare(altered)
        assert raised.value.code == code


def test_native_errorbar_properties_and_failure_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    plot = {"ErrorBars": {"HorzBarType": 0, "VertBarType": 0}}
    monkeypatch.setattr(error_bar, "get", lambda obj, name: obj[name])
    monkeypatch.setattr(error_bar, "put", lambda obj, name, value: obj.__setitem__(name, value))
    assert error_bar.read_y_error(plot) == {"present": False}
    error_bar.add_y_error(plot, 3)
    assert error_bar.read_y_error(plot) == {
        "present": True,
        "column_index": 3,
        "direction": "y",
        "symmetric": True,
    }
    plot["ErrorBars"]["VertBarDirection"] = 1
    with pytest.raises(EngineError) as raised:
        error_bar.read_y_error(plot)
    assert raised.value.code == "grapher_errorbar_readback_failed"


def test_verify_rejects_wrong_native_error_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name, signature in (("result.grf", b"Grapher"), ("result.png", b"\x89PNG"), ("result.pdf", b"%PDF")):
        (tmp_path / name).write_bytes(signature)
    staging = tmp_path / "grapher_staging.csv"
    staging.write_text("Time,Control,Control_SD,Treatment,Treatment_SD\n0,10,1,11,2\n", encoding="utf-8-sig")
    expected = {
        "chart_type": "xy_line",
        "x_column": "Time",
        "y_columns": ["Control", "Treatment"],
        "y_errors": {"Control": {"column": "Control_SD"}, "Treatment": {"column": "Treatment_SD"}},
        "x_title": "Time",
        "y_title": "Value",
    }
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "staging": {
                    "path": str(staging),
                    "sha256": hashlib.sha256(staging.read_bytes()).hexdigest(),
                    "columns": ["Time", "Control", "Control_SD", "Treatment", "Treatment_SD"],
                },
                "expected": expected,
            }
        ),
        encoding="utf-8",
    )
    plots = [
        {
            "type": "xy_line",
            "name": "Control",
            "x_column_index": 1,
            "y_column_index": 2,
            "worksheet": str(staging),
            "line_enabled": True,
            "error": {
                "present": True,
                "column": "Control_SD",
                "column_index": 3,
                "direction": "y",
                "symmetric": True,
            },
        },
        {
            "type": "xy_line",
            "name": "Treatment",
            "x_column_index": 1,
            "y_column_index": 4,
            "worksheet": str(staging),
            "line_enabled": True,
            "error": {
                "present": True,
                "column": "Control_SD",
                "column_index": 3,
                "direction": "y",
                "symmetric": True,
            },
        },
    ]
    engine = GrapherEngine()
    monkeypatch.setattr(
        engine,
        "readback",
        lambda _path: {
            "document": {"opened": True},
            "graph_count": 1,
            "plots": plots,
            "legends": [{"entries": ["Control", "Treatment"]}],
            "axes": {"x": {"title": "Time"}, "y": {"title": "Value"}},
        },
    )
    assert engine.verify(tmp_path)["checks"]["error_bindings"] is False
    plots[1]["error"].update(column="Treatment_SD", column_index=5)
    assert engine.verify(tmp_path)["status"] == "ok"
