"""Attach-or-own regression checks; native tests never touch preexisting user processes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "runtime" / "src", ROOT / "skill" / "figureloom" / "scripts"):
    sys.path.insert(0, str(directory))

from grapher_sciplot import smoke  # noqa: E402


class NoActiveObject(Exception):
    hresult = -2147221021


@pytest.fixture
def native_fakes(monkeypatch: pytest.MonkeyPatch):
    calls = []
    state = {"pids": {42}, "visible": True, "count": 1, "alive": True}
    app = object()
    monkeypatch.setattr(smoke, "discover", lambda: {"executable": "Grapher.exe", "progid": smoke.PROGID})
    monkeypatch.setattr(smoke, "grapher_pids", lambda: set(state["pids"]))
    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(
        CoInitialize=lambda: calls.append("initialize"),
        CoUninitialize=lambda: calls.append("uninitialize"), com_error=NoActiveObject,
    ))
    monkeypatch.setitem(sys.modules, "win32com.client", SimpleNamespace(
        GetActiveObject=lambda _name: (_ for _ in ()).throw(NoActiveObject()),
        DispatchEx=lambda _name: app,
    ))

    def start(_exe):
        calls.append("start")
        state["pids"] = {42}
        return SimpleNamespace(pid=42, poll=lambda: None if state["alive"] else 0,
                               wait=lambda **_kwargs: calls.append("wait"))

    monkeypatch.setattr(smoke, "_start_application", start)
    monkeypatch.setattr(smoke, "get", lambda _obj, name: {
        "Version": "27.1.296", "Visible": state["visible"], "Documents": object(),
        "Count": state["count"], "FullName": "Grapher.exe",
    }[name])
    monkeypatch.setattr(smoke, "put", lambda _obj, name, value: calls.append((name, value)))
    monkeypatch.setattr(smoke, "quit_owned_application", lambda *_args: calls.append("Quit"))
    monkeypatch.setattr(smoke.os, "kill", lambda *_args: pytest.fail("No PID may be killed"))
    return state, calls, app


@pytest.mark.parametrize("fail", [False, True])
def test_existing_window_is_never_hidden_or_quit(native_fakes, fail):
    state, calls, _app = native_fakes
    try:
        with smoke.application(visible=False) as (_connected, info):
            assert info["ownership"] is False
            assert info["connection_mode"] == "attach"
            assert info["visible"] is True
            if fail:
                raise ValueError("drawing failed")
    except smoke.SmokeFailure as exc:
        assert fail
        assert isinstance(exc.__cause__, ValueError)
    assert calls == ["initialize", "uninitialize"]
    assert state["pids"] == {42}


def test_new_verified_child_is_owned_and_quit(native_fakes):
    state, calls, _app = native_fakes
    state.update(pids=set(), visible=False, count=0)
    with smoke.application(visible=True) as (_connected, info):
        assert info["ownership"] is True
        assert info["pid"] == 42
    assert calls == ["initialize", "start", ("Visible", True), "Quit", "uninitialize", "wait"]


def test_owned_shutdown_timeout_is_reported_without_killing(native_fakes, monkeypatch):
    state, calls, _app = native_fakes
    state.update(pids=set(), visible=False, count=0)

    def start(_exe):
        state["pids"] = {42}
        return SimpleNamespace(pid=42, poll=lambda: None,
                               wait=lambda **_kwargs: (_ for _ in ()).throw(
                                   subprocess.TimeoutExpired("Grapher", 10)))

    monkeypatch.setattr(smoke, "_start_application", start)
    with pytest.raises(smoke.SmokeFailure) as error:
        with smoke.application(visible=False):
            pass
    assert error.value.code == "grapher_cleanup_failed"
    assert "Quit" in calls and "uninitialize" in calls


@pytest.mark.parametrize("change", ["extra_process", "exited_child", "user_document"])
def test_ambiguous_activation_is_released_without_quit(native_fakes, monkeypatch, change):
    state, calls, _app = native_fakes
    state.update(pids=set(), visible=False, count=0)
    def start(_exe):
        state["pids"] = {42, 99} if change == "extra_process" else {42}
        state["count"] = int(change == "user_document")
        return SimpleNamespace(pid=42, poll=lambda: 0 if change == "exited_child" else None)
    monkeypatch.setattr(smoke, "_start_application", start)
    with pytest.raises(smoke.SmokeFailure) as error:
        with smoke.application(visible=False):
            pytest.fail("Ambiguous ownership must stop before drawing")
    assert error.value.code == "grapher_ownership_unverified"
    assert "Quit" not in calls


def test_user_document_opened_during_owned_job_prevents_quit(native_fakes):
    state, calls, _app = native_fakes
    state.update(pids=set(), visible=False, count=0)
    with pytest.raises(smoke.SmokeFailure) as error:
        with smoke.application(visible=False):
            state["count"] = 1
    assert error.value.code == "grapher_cleanup_failed"
    assert "Quit" not in calls


def test_already_open_grf_is_not_acquired_or_closed(monkeypatch, tmp_path):
    path = tmp_path / "user.grf"
    calls = []
    monkeypatch.setattr(smoke, "get", lambda _obj, name: {
        "Documents": object(), "Count": 1, "FullName": str(path),
    }[name])
    monkeypatch.setattr(smoke, "call", lambda _obj, name, *_args: calls.append(name))
    with pytest.raises(smoke.SmokeFailure) as error:
        smoke.open_document(object(), path)
    assert error.value.code == "grapher_document_in_use"
    assert calls == ["Item"]


@pytest.mark.parametrize("already_open", [False, True])
@pytest.mark.parametrize("read_fails", [False, True])
def test_heatmap_readback_preserves_existing_worksheet(monkeypatch, tmp_path, already_open, read_fails):
    from grapher_sciplot import correlation_heatmap as heatmap

    plot, worksheet, used = (object() for _ in range(3))
    path = str(tmp_path / "correlation_cells.csv")
    preexisting_paths = {Path(path).resolve()} if already_open else set()
    closed = []

    def get(obj, name):
        if name == "Value" and read_fails:
            raise ValueError("worksheet read failed")
        return {(plot, "worksheet"): path,
                (worksheet, "UsedRange"): used, (used, "Value"): ((1, 2),)}[obj, name]

    def call(obj, name, *_args):
        if name == "Close":
            closed.append(obj)
        else:
            return worksheet

    monkeypatch.setattr(heatmap, "get", get)
    monkeypatch.setattr(heatmap, "call", call)
    if read_fails:
        with pytest.raises(ValueError, match="worksheet read failed"):
            heatmap._worksheet_values(plot, preexisting_paths)
    else:
        assert heatmap._worksheet_values(plot, preexisting_paths) == ((1, 2),)
    assert closed == ([] if already_open else [worksheet])


def test_pywin32_is_direct_and_all_dependency_copies_match():
    import figureloom_core as core

    assert ("pythoncom", "pywin32==312") in core.RUNTIME_DEPENDENCIES
    direct = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")
    lock = (ROOT / "requirements-runtime.lock").read_text(encoding="utf-8")
    assert "pywin32==312" in direct.splitlines()
    assert "pywin32==312" in lock.splitlines()
    assert direct == (ROOT / "runtime" / "requirements-runtime.txt").read_text(encoding="utf-8")
    for path in (ROOT / "runtime" / "requirements-runtime.lock",
                 ROOT / "skill" / "figureloom" / "scripts" / "requirements-runtime.lock"):
        assert lock == path.read_text(encoding="utf-8")
    assert '"pywin32==312"' in (ROOT / "runtime" / "pyproject.toml").read_text(encoding="utf-8")


def test_doctor_identifies_missing_pywin32_without_activation(monkeypatch):
    from grapher_sciplot.engine import GrapherEngine

    engine = GrapherEngine()
    monkeypatch.setattr(engine, "detect", lambda: {
        "version": "27.1.296", "progid": smoke.PROGID, "executable": "Grapher.exe",
    })
    monkeypatch.setitem(sys.modules, "pythoncom", None)
    result = engine.doctor()
    assert result["installed"] is True
    assert result["ready_for_render"] is False
    assert result["missing_dependencies"] == ["pywin32==312"]


def test_grapher_doctor_repair_uses_locked_project_environment(monkeypatch, capsys):
    import figureloom as cli

    monkeypatch.setattr(cli, "_selected_engine", lambda _args: SimpleNamespace(
        doctor=lambda **_kwargs: {"ready_for_render": False, "missing_dependencies": ["pywin32==312"]},
    ))
    calls = []
    monkeypatch.setattr(cli, "repair_environment", lambda **kwargs: calls.append(kwargs) or {"ok": True})
    assert cli.main(["doctor", "--engine", "grapher", "--repair"]) == 0
    assert calls == [{"engine_home": None}]
    assert json.loads(capsys.readouterr().out)["repair"]["ok"] is True


@pytest.mark.grapher
@pytest.mark.skipif(os.name != "nt", reason="Windows COM required")
def test_real_desktop_window_survives_smoke_doctor_render_verify_and_edit(tmp_path):
    import figureloom_core as core
    import pythoncom
    from grapher_sciplot.engine import GrapherEngine
    from win32com.client import DispatchEx

    pytest.importorskip("pythoncom")
    try:
        registration = smoke.discover()
    except smoke.SmokeFailure as exc:
        pytest.skip(str(exc))
    existing = smoke.grapher_pids()
    if len(existing) > 1:
        pytest.skip("Multiple user processes: no window is touched")
    # /Automation avoids interactive startup prompts; after becoming visible this is
    # an existing desktop session from the backend's point of view.
    process = smoke._start_application(registration["executable"]) if not existing else None
    expected_pids = existing or {process.pid}
    pythoncom.CoInitialize()
    app = sentinel = marker = None
    try:
        for attempt in range(40):
            try:
                app = DispatchEx(smoke.PROGID)
                break
            except pythoncom.com_error:
                if attempt == 39:
                    raise
                time.sleep(0.25)
        assert smoke.grapher_pids() == expected_pids
        if process is not None:
            smoke.put(app, "Visible", True)
        sentinel = smoke.call(smoke.get(app, "Documents"), "Add", 0)
        marker = smoke.call(smoke.get(sentinel, "Shapes"), "AddText", 1.0, 1.0, "unsaved user content")
        original_count = int(smoke.get(smoke.get(app, "Documents"), "Count"))
        original_visible = bool(smoke.get(app, "Visible"))
        sentinel_name = str(smoke.get(sentinel, "Name"))
        marker = sentinel = app = None
        report = smoke.run_smoke(tmp_path / "smoke", visible=False)
        assert report["status"] == "ok", report
        assert report["application"]["ownership"] is False
        assert report["readback"]["plot_count"] == 1
        doctor = subprocess.run(
            [sys.executable, "-m", "figureloom_engine.doctor_probe", "grapher"],
            env={**os.environ, "PYTHONPATH": str(ROOT / "runtime" / "src")},
            capture_output=True, text=True, check=False,
        )
        assert doctor.returncode == 0, doctor.stdout
        assert json.loads(doctor.stdout)["shutdown_requested"] is False
        source = ROOT / "docs" / "quickstart-data" / "multiseries.csv"
        mapping = {"assignments": {"X": "x", "Control": "series", "Treatment": "series"}}
        understanding = core.understand_data(source, template_id="trend", mapping=mapping,
                                            engine_home=ROOT / "runtime")
        plan = core.build_plan(source, template_id="trend", claim="Native attach regression",
                               evidence_role="trend", mapping=mapping,
                               semantic_confirmation=understanding["confirmation_gate"][
                                   "confirmation_payload_template"], engine_home=ROOT / "runtime")
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        engine = GrapherEngine()
        result = engine.render(plan, plan_file=plan_path, output_dir=tmp_path / "render")
        assert result.status == "ok"
        assert engine.verify(result.output_dir)["status"] == "ok"
        edited = engine.apply_edit(result.editable_path,
                                   {"operation": "set_axis_title", "axis": "y", "value": "Edited Y"})
        assert edited["status"] == "ok"
        assert smoke.grapher_pids() == expected_pids
        # This build invalidates older proxies after another COM activation. Reacquire
        # live objects to inspect the unchanged user document, rather than stale proxies.
        app = DispatchEx(smoke.PROGID)
        assert bool(smoke.get(app, "Visible")) is original_visible
        documents = smoke.get(app, "Documents")
        sentinel = next(document for index in range(1, int(smoke.get(documents, "Count")) + 1)
                        if str(smoke.get(document := smoke.call(documents, "Item", index), "Name"))
                        == sentinel_name)
        marker = smoke.call(smoke.get(sentinel, "Shapes"), "Item", 1)
        assert int(smoke.get(smoke.get(app, "Documents"), "Count")) == original_count
        assert smoke.get(marker, "Text") == "unsaved user content"
    finally:
        if sentinel is not None:
            smoke.call(sentinel, "Close", False)
        marker = sentinel = documents = document = None
        # Only this test's explicit child may be quit; existing user windows are retained.
        if (app is not None and process is not None and process.poll() is None
                and smoke.grapher_pids() == {process.pid}):
            smoke.call(app, "Quit")
        app = None
        pythoncom.CoUninitialize()
        if process is not None:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pytest.fail("Harness-owned desktop did not exit; left untouched")
