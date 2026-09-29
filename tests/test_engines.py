from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "skill" / "figureloom" / "scripts", ROOT / "runtime" / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import figureloom as cli  # noqa: E402
import figureloom_core as core  # noqa: E402
from figureloom_engine import DEFAULT_ENGINE, EngineError, get_engine  # noqa: E402
from figureloom_engine.origin import OriginEngine  # noqa: E402
from grapher_sciplot.engine import GrapherEngine, _plot_mode, _visual_mode  # noqa: E402
from grapher_sciplot.smoke import SmokeFailure  # noqa: E402


def test_engine_registry_selects_default_and_named_backends() -> None:
    assert DEFAULT_ENGINE == "origin"
    assert isinstance(get_engine(), OriginEngine)
    assert isinstance(get_engine("origin"), OriginEngine)
    assert isinstance(get_engine("grapher"), GrapherEngine)


def test_engine_registry_rejects_unknown_backend() -> None:
    with pytest.raises(EngineError) as raised:
        get_engine("photoshop")

    assert raised.value.code == "unknown_engine"
    assert raised.value.details["available_engines"] == ["origin", "grapher"]


def test_grapher_errors_use_engine_neutral_envelope() -> None:
    payload = SmokeFailure("grapher_com_activation_failed", "COM unavailable").to_dict()
    assert payload == {
        "status": "failed",
        "engine": "grapher",
        "error": {"code": "grapher_com_activation_failed", "message": "COM unavailable"},
    }


def test_grapher_doctor_does_not_activate_com(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = GrapherEngine()
    monkeypatch.setattr(
        engine,
        "detect",
        lambda: {
            "progid": "Grapher.Application",
            "executable": "Grapher.exe",
            "version": "27.1.296.0",
        },
    )
    for module in ("pythoncom", "win32api", "win32com", "win32com.client"):
        monkeypatch.setitem(sys.modules, module, SimpleNamespace())

    report = engine.doctor()

    assert report["engine"] == "grapher"
    assert report["ready_for_render"] is True
    assert report["fit_capabilities"]["explicit_weight"] is False


def test_grapher_prepares_csv_from_backend_neutral_render_spec(tmp_path: Path) -> None:
    source = tmp_path / "实验数据.csv"
    source.write_text("X,Y\n1,1\n2,4\n", encoding="utf-8")
    plan = {
        "template": {"id": "scatter"},
        "source": {"path": str(source), "sheet": None},
        "render_spec": {
            "chart_type": "xy_scatter",
            "data": {"x": "X", "y": ["Y"]},
        },
    }

    render_spec, frame = GrapherEngine._prepare(plan)

    assert render_spec["data"] == {"x": "X", "y": ["Y"]}
    assert frame.to_dict(orient="list") == {"X": [1, 2], "Y": [1, 4]}


@pytest.mark.parametrize("series", [("Control",), ("Control", "Treatment")])
def test_trend_plan_selects_xy_line_and_preserves_series_order(
    tmp_path: Path, series: tuple[str, ...]
) -> None:
    source = tmp_path / "time.csv"
    source.write_text(
        "Time,Control,Treatment\n0,10,11\n1,14,16\n2,18,22\n",
        encoding="utf-8",
    )
    mapping = {
        "assignments": {
            "Time": "x",
            "Control": "series",
            "Treatment": "series" if "Treatment" in series else "ignored",
        }
    }
    understanding = core.understand_data(
        source, template_id="trend", mapping=mapping, engine_home=ROOT / "runtime"
    )
    plan = core.build_plan(
        source,
        template_id="trend",
        claim="Values increase with time.",
        evidence_role="trend",
        mapping=mapping,
        semantic_confirmation=understanding["confirmation_gate"]["confirmation_payload_template"],
        engine_home=ROOT / "runtime",
    )
    assert plan["render_spec"]["chart_type"] == "xy_line"
    assert plan["render_spec"]["data"] == {"x": "Time", "y": list(series)}
    assert plan["render_spec"]["style"]["line_width_pt"] > 0
    _, frame = GrapherEngine._prepare(plan)
    assert list(frame.columns) == ["Time", *series]


def test_xy_style_and_readback_modes() -> None:
    assert _visual_mode("xy_scatter", {}) == (1, 0.0)
    assert _plot_mode(1, "Invisible") == "xy_scatter"
    symbols, width = _visual_mode("xy_line", {"line_width_pt": 2.0})
    assert symbols == 0
    assert width == pytest.approx(2.0 / 72.0)
    assert _plot_mode(symbols, "Solid") == "xy_line"
    assert _visual_mode("xy_line", {"show_symbols": True})[0] == 1


def test_grapher_verify_uses_native_signatures_and_semantic_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "result.grf").write_bytes(b"Grapher native")
    (tmp_path / "result.png").write_bytes(b"\x89PNG native")
    (tmp_path / "result.pdf").write_bytes(b"%PDF native")
    staging = tmp_path / "grapher_staging.csv"
    staging.write_text("X,Y\n1,2\n", encoding="utf-8-sig")
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "staging": {
                    "path": str(staging),
                    "sha256": hashlib.sha256(staging.read_bytes()).hexdigest(),
                },
                "expected": {
                    "chart_type": "xy_scatter",
                    "x_column": "X",
                    "y_columns": ["Y"],
                    "x_title": "Time",
                    "y_title": "Response",
                }
            }
        ),
        encoding="utf-8",
    )
    engine = GrapherEngine()
    monkeypatch.setattr(
        engine,
        "readback",
        lambda _artifact: {
            "document": {"opened": True},
            "graph_count": 1,
            "plots": [
                {
                    "type": "xy_scatter",
                    "name": "Y",
                    "x_column_index": 1,
                    "y_column_index": 2,
                    "worksheet": str(staging),
                    "symbol_frequency": 1,
                    "line_enabled": False,
                }
            ],
            "legends": [],
            "axes": {"x": {"title": "Time"}, "y": {"title": "Response"}},
        },
    )

    report = engine.verify(tmp_path)

    assert report["status"] == "ok"
    assert report["checks"] == {
        "files_nonempty": True,
        "native_signatures": True,
        "staging_integrity": True,
        "document_reopened": True,
        "plot_binding": True,
        "line_symbol_mode": True,
        "chart_mode": True,
        "category_binding": True,
        "legend_labels": True,
        "series_colors": True,
        "graph_title": True,
        "axes": True,
        "error_bindings": True,
    }


def test_grapher_verify_rejects_missing_second_line_and_wrong_legend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, contents in (
        ("result.grf", b"Grapher native"),
        ("result.png", b"\x89PNG native"),
        ("result.pdf", b"%PDF native"),
    ):
        (tmp_path / name).write_bytes(contents)
    staging = tmp_path / "grapher_staging.csv"
    staging.write_text("Time,Control,Treatment\n0,10,11\n", encoding="utf-8-sig")
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "staging": {
                    "path": str(staging),
                    "sha256": hashlib.sha256(staging.read_bytes()).hexdigest(),
                },
                "expected": {
                    "chart_type": "xy_line",
                    "x_column": "Time",
                    "y_columns": ["Control", "Treatment"],
                    "x_title": "Time",
                    "y_title": "Response",
                },
            }
        ),
        encoding="utf-8",
    )
    engine = GrapherEngine()
    monkeypatch.setattr(
        engine,
        "readback",
        lambda _artifact: {
            "document": {"opened": True},
            "graph_count": 1,
            "plots": [
                {
                    "type": "xy_line",
                    "name": "Control",
                    "x_column_index": 1,
                    "y_column_index": 2,
                    "worksheet": str(staging),
                    "line_enabled": True,
                }
            ],
            "legends": [{"entries": ["Control", "Plot 2"]}],
            "axes": {"x": {"title": "Time"}, "y": {"title": "Response"}},
        },
    )
    report = engine.verify(tmp_path)
    assert report["status"] == "failed"
    assert report["checks"]["plot_binding"] is False
    assert report["checks"]["legend_labels"] is False


def test_cli_dispatches_render_and_verify_to_selected_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    plan_file = tmp_path / "plan.json"
    plan_file.write_text("{}", encoding="utf-8")
    calls: list[str] = []

    class FakeEngine:
        name = "grapher"

        def render(self, *_args: object, **_kwargs: object) -> SimpleNamespace:
            calls.append("render")
            return SimpleNamespace(to_dict=lambda: {"status": "ok", "engine": "grapher"})

        def verify(self, _output: str) -> dict[str, str]:
            calls.append("verify")
            return {"status": "ok", "engine": "grapher"}

    monkeypatch.setattr(cli, "_selected_engine", lambda _args: FakeEngine())

    assert cli.main(["render", str(plan_file), "--engine", "grapher"]) == 0
    assert cli.main(["verify", str(tmp_path), "--engine", "grapher"]) == 0
    assert calls == ["render", "verify"]
    assert capsys.readouterr().out.count('"engine": "grapher"') == 2


def test_cli_grapher_verify_failure_has_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "_selected_engine",
        lambda _args: SimpleNamespace(
            verify=lambda _output: {"status": "failed", "engine": "grapher"}
        ),
    )
    assert cli.main(["verify", str(tmp_path), "--engine", "grapher"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_cli_unknown_engine_is_structured(capsys: pytest.CaptureFixture[str]) -> None:
    return_code = cli.main(
        [
            "doctor",
            "--engine",
            "photoshop",
            "--engine-home",
            str(ROOT / "runtime"),
        ]
    )

    payload = json.loads(capsys.readouterr().err)
    assert return_code == 2
    assert payload["error"]["code"] == "unknown_engine"
    assert payload["error"]["available_engines"] == ["origin", "grapher"]
