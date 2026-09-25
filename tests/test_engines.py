from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "skill" / "editaplot" / "scripts", ROOT / "runtime" / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import editaplot as cli  # noqa: E402
from editaplot_engine import DEFAULT_ENGINE, EngineError, get_engine  # noqa: E402
from editaplot_engine.origin import OriginEngine  # noqa: E402
from grapher_sciplot.engine import GrapherEngine  # noqa: E402
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
            "executable": "C:/Grapher.exe",
            "version": "27.1.296.0",
        },
    )
    monkeypatch.setattr("grapher_sciplot.engine.importlib.util.find_spec", lambda _name: object())

    report = engine.doctor()

    assert report["engine"] == "grapher"
    assert report["ready_for_render"] is True


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


def test_grapher_verify_uses_native_signatures_and_semantic_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "result.grf").write_bytes(b"Grapher native")
    (tmp_path / "result.png").write_bytes(b"\x89PNG native")
    (tmp_path / "result.pdf").write_bytes(b"%PDF native")
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "expected": {
                    "x_column": "X",
                    "y_column": "Y",
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
            "plots": [{"type": "xy_scatter", "x_column_index": 1, "y_column_index": 2}],
            "axes": {"x": {"title": "Time"}, "y": {"title": "Response"}},
        },
    )

    report = engine.verify(tmp_path)

    assert report["status"] == "ok"
    assert report["checks"] == {
        "files_nonempty": True,
        "native_signatures": True,
        "document_reopened": True,
        "plot_binding": True,
        "axes": True,
    }


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
