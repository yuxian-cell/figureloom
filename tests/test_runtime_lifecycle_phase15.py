"""Safe native application shutdown boundaries."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "src"))
sys.path.insert(0, str(ROOT / "skill" / "figureloom" / "scripts"))


def test_grapher_quit_never_terminates_pid_from_process_difference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from grapher_sciplot import smoke

    calls: list[str] = []
    monkeypatch.setattr(smoke, "grapher_pids", lambda: {42})
    monkeypatch.setattr(smoke, "call", lambda _app, name: calls.append(name))
    monkeypatch.setattr(smoke.os, "kill", lambda *_args: pytest.fail("must not kill a PID"))

    outcome = smoke.quit_owned_application(object(), 42)

    assert calls == ["Quit"]
    assert outcome is None


def test_attached_origin_session_detaches_without_exiting_user_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from origin_sciplot.origin_backend.capabilities import ConnectionMode
    from origin_sciplot.origin_backend.session import OriginSession

    calls: list[str] = []
    origin = SimpleNamespace(
        oext=True,
        attach=lambda: calls.append("attach"),
        detach=lambda: calls.append("detach"),
        exit=lambda: pytest.fail("must not exit an attached Origin"),
        lt_float=lambda _name: 10.15,
    )
    monkeypatch.setitem(sys.modules, "originpro", origin)

    with OriginSession(connection_mode=ConnectionMode.ATTACH_EXISTING) as session:
        assert session.ownership.value == "user"

    assert calls == ["attach", "detach"]


def test_origin_cleanup_warning_preserves_primary_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from origin_sciplot.origin_backend.capabilities import ConnectionMode
    from origin_sciplot.origin_backend.session import OriginSession

    def fail_detach() -> None:
        raise RuntimeError("detach failed")

    origin = SimpleNamespace(oext=True, attach=lambda: None, detach=fail_detach,
                             lt_float=lambda _name: 10.15)
    monkeypatch.setitem(sys.modules, "originpro", origin)
    with pytest.raises(ValueError, match="primary") as error:
        with OriginSession(connection_mode=ConnectionMode.ATTACH_EXISTING):
            raise ValueError("primary")
    assert "origin_detach_failed" in " ".join(error.value.__notes__)


def test_grapher_cleanup_warning_preserves_primary_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from figureloom_engine.models import EngineError
    from grapher_sciplot import engine, smoke

    class Unavailable(Exception):
        hresult = -2147221021

    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(
        CoInitialize=lambda: None, CoUninitialize=lambda: None, com_error=Unavailable,
    ))
    monkeypatch.setitem(sys.modules, "win32com.client", SimpleNamespace(
        GetActiveObject=lambda _progid: (_ for _ in ()).throw(Unavailable()),
        DispatchEx=lambda _progid: object(),
    ))
    states = iter((set(), {42}, {42}))
    monkeypatch.setattr(smoke, "grapher_pids", lambda: next(states))
    monkeypatch.setattr(smoke, "_start_application", lambda _exe: SimpleNamespace(pid=42, poll=lambda: None))
    monkeypatch.setattr(smoke, "put", lambda *_args: None)
    monkeypatch.setattr(smoke, "get", lambda _app, name: {
        "Version": "27", "Visible": False, "Documents": object(), "Count": 0,
        "FullName": "Grapher.exe",
    }[name])
    monkeypatch.setattr(smoke, "discover", lambda: {"progid": "Grapher.Application",
                                                  "executable": "Grapher.exe"})
    monkeypatch.setattr(smoke, "quit_owned_application", lambda *_args: "COM Quit timed out")

    with pytest.raises(EngineError) as error:
        with engine._application(visible=False):
            raise EngineError("edit_target_not_found", "Series missing", engine="grapher")

    assert error.value.code == "edit_target_not_found"
    assert "COM Quit timed out" in " ".join(error.value.__notes__)


def test_interrupted_session_and_failed_edit_are_not_reported_as_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from figureloom_engine import workflow
    from figureloom_engine.models import EngineError

    source = tmp_path / "data.csv"
    source.write_text("X,Y\n1,2\n", encoding="utf-8")
    artifact = tmp_path / "result.grf"
    artifact.write_bytes(b"native project placeholder")
    path = tmp_path / "session.json"
    session = {
        "status": "editing", "engine": "grapher",
        "source": {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        "artifacts": {"editable": str(artifact), "exports": {}}, "edits": [],
    }
    path.write_text(json.dumps(session), encoding="utf-8")
    edit = {"operation": "set_axis_title", "axis": "y", "value": "Current"}
    with pytest.raises(EngineError) as error:
        workflow.edit_session(path, edit)
    assert error.value.code == "incomplete_session"

    session["status"] = "verified"
    path.write_text(json.dumps(session), encoding="utf-8")

    def fail_edit(_artifact: Path, _edit: dict[str, str]) -> None:
        raise EngineError("edit_target_not_found", "Axis missing", engine="grapher")

    monkeypatch.setattr(workflow, "get_engine", lambda _name: SimpleNamespace(
        name="grapher", apply_edit=fail_edit,
    ))
    with pytest.raises(EngineError) as error:
        workflow.edit_session(path, edit, request="Change Y title")
    assert error.value.code == "edit_target_not_found"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["status"] == "edit_failed"
    assert saved["edits"][-1]["status"] == "failed"
    assert "applied_at" not in saved["edits"][-1]


def test_failed_native_verify_leaves_failed_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from figureloom_engine import workflow
    from figureloom_engine.models import EngineError

    source = ROOT / "tests" / "fixtures" / "phase14" / "experiment_multiseries.csv"
    run = tmp_path / "run"
    workflow.preview(source, run, engine_name="grapher", template_id="trend",
                     engine_home=ROOT / "runtime")
    fake = SimpleNamespace(
        name="grapher",
        doctor=lambda **_kwargs: {"ready_for_render": True},
        render=lambda *_args, **_kwargs: SimpleNamespace(status="ok", output_dir=run / "grapher",
                                                        metadata={"engine_version": "27"}),
        verify=lambda _output_dir: {"status": "failed"},
    )
    monkeypatch.setattr(workflow, "get_engine", lambda _name: fake)

    with pytest.raises(EngineError) as error:
        workflow.render_confirmed(run / "workflow-preview.json", claim="comparison", confirmed=True)

    assert error.value.code == "verify_failed"
    saved = json.loads((run / "session.json").read_text(encoding="utf-8"))
    assert saved["status"] == "failed"
    assert saved["artifacts"] is None
    assert saved["verification"]["status"] == "failed"


def test_workflow_output_failure_is_structured(tmp_path: Path) -> None:
    from figureloom_engine import workflow
    from figureloom_engine.models import EngineError

    blocked = tmp_path / "not-a-directory"
    blocked.write_text("occupied", encoding="utf-8")
    with pytest.raises(EngineError) as error:
        workflow.preview(ROOT / "tests" / "fixtures" / "phase14" /
                         "experiment_multiseries.csv", blocked)
    assert error.value.code == "output_unwritable"


def test_edit_verify_failure_cannot_become_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from figureloom_engine import workflow
    from figureloom_engine.models import EngineError

    source = tmp_path / "source.csv"
    source.write_text("X,Y\n1,2\n", encoding="utf-8")
    artifact = tmp_path / "result.grf"
    artifact.write_bytes(b"placeholder")
    session_path = tmp_path / "session.json"
    session_path.write_text(json.dumps({
        "status": "verified", "engine": "grapher",
        "source": {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        "artifacts": {"editable": str(artifact), "exports": {}}, "edits": [],
    }), encoding="utf-8")
    monkeypatch.setattr(workflow, "get_engine", lambda _name: SimpleNamespace(
        name="grapher", apply_edit=lambda *_args: {"status": "failed"},
    ))
    with pytest.raises(EngineError) as error:
        workflow.edit_session(session_path, {"operation": "set_axis_title", "axis": "y",
                                             "value": "Current"})
    assert error.value.code == "edit_verify_failed"
    saved = json.loads(session_path.read_text(encoding="utf-8"))
    assert saved["status"] == "edit_failed"
    assert saved["edits"][-1]["status"] == "failed"


def test_live_doctor_failure_is_reported_without_native_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import figureloom as cli

    monkeypatch.setattr(cli, "_native_pids", lambda _engine: set())
    monkeypatch.setattr(cli.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(
        stdout='{"engine":"grapher","automation":"failed","error":{"code":'
               '"grapher_unavailable","message":"Activation failed"}}\n',
        returncode=2,
    ))
    result = cli._live_doctor("grapher")
    assert result["automation"] == "failed"
    assert result["error"]["code"] == "grapher_unavailable"
    assert result["shutdown"] == "clean_shutdown"


def test_missing_input_sheet_and_backend_availability_are_distinct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from figureloom_engine import workflow
    from figureloom_engine.models import EngineError

    select_engine = workflow.get_engine
    with pytest.raises(EngineError) as error:
        workflow.preview(tmp_path / "missing.csv", tmp_path / "missing-run")
    assert error.value.code == "file_not_found"
    with pytest.raises(EngineError) as error:
        workflow.preview(ROOT / "docs" / "quickstart-data" / "error.xlsx", tmp_path / "bad-sheet",
                         sheet="Absent", engine_home=ROOT / "runtime")
    assert error.value.code == "sheet_not_found"

    source = ROOT / "docs" / "quickstart-data" / "multiseries.csv"
    workflow.preview(source, tmp_path / "unavailable", engine_name="grapher",
                     template_id="trend", engine_home=ROOT / "runtime")
    monkeypatch.setattr(workflow, "get_engine", lambda _name: SimpleNamespace(
        name="grapher", doctor=lambda **_kwargs: {"ready_for_render": False},
    ))
    with pytest.raises(EngineError) as error:
        workflow.render_confirmed(tmp_path / "unavailable" / "workflow-preview.json",
                                  claim="comparison", confirmed=True)
    assert error.value.code == "grapher_unavailable"

    monkeypatch.setattr(workflow, "get_engine", select_engine)
    workflow.preview(source, tmp_path / "origin-unavailable", engine_name="origin",
                     template_id="trend", engine_home=ROOT / "runtime")
    monkeypatch.setattr(workflow, "get_engine", lambda _name: SimpleNamespace(
        name="origin", doctor=lambda **_kwargs: {"ready_for_render": False},
    ))
    with pytest.raises(EngineError) as error:
        workflow.render_confirmed(tmp_path / "origin-unavailable" / "workflow-preview.json",
                                  claim="comparison", confirmed=True)
    assert error.value.code == "origin_unavailable"


def test_verbose_runtime_log_keeps_native_diagnostic_without_table_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from figureloom_engine.workflow import _log

    monkeypatch.setenv("FIGURELOOM_VERBOSE", "1")
    _log(tmp_path, {"run_id": "run-1", "engine": "grapher",
                    "recommendation": {"selected_template_id": "trend"}},
         "render_failed", RuntimeError("HRESULT 0x800706be"))
    event = json.loads((tmp_path / "runtime.log").read_text(encoding="utf-8"))
    assert event["run_id"] == "run-1"
    assert event["route"] == "trend"
    assert "HRESULT 0x800706be" in event["native_trace"]


def test_verified_session_matches_plan_source_artifacts_and_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from figureloom_engine import workflow
    from figureloom_engine.models import RenderResult

    source = ROOT / "docs" / "quickstart-data" / "multiseries.csv"
    run = tmp_path / "run"
    workflow.preview(source, run, engine_name="grapher", template_id="trend",
                     engine_home=ROOT / "runtime")

    def render(_plan: dict, **_kwargs: object) -> RenderResult:
        output = run / "grapher"
        output.mkdir()
        editable, png, pdf = (output / name for name in ("result.grf", "result.png", "result.pdf"))
        for path in (editable, png, pdf):
            path.write_bytes(b"fixture")
        return RenderResult("grapher", "ok", output, editable, {"png": png, "pdf": pdf},
                            {"native_graph_count": 1}, {"engine_version": "27"})

    monkeypatch.setattr(workflow, "get_engine", lambda _name: SimpleNamespace(
        name="grapher", doctor=lambda **_kwargs: {"ready_for_render": True},
        render=render, verify=lambda _output: {"status": "ok"},
    ))
    session = workflow.render_confirmed(run / "workflow-preview.json", claim="comparison",
                                        confirmed=True)
    plan = json.loads((run / "render-plan.json").read_text(encoding="utf-8"))
    assert session["status"] == "verified"
    assert session["verification"]["status"] == "ok"
    assert session["plan"]["hash"] == plan["plan_hash"]
    assert session["source"]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert session["current_readback"] == session["artifacts"]["readback"]
    assert all(Path(path).is_file() for path in session["artifacts"]["exports"].values())
