from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "src"))
sys.path.insert(0, str(ROOT / "skill" / "figureloom" / "scripts"))

import figureloom as cli  # noqa: E402
from grapher_sciplot import smoke  # noqa: E402


def test_discovery_reports_missing_install_or_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smoke.platform, "system", lambda: "Windows")
    monkeypatch.setenv("ProgramFiles", str(ROOT / "missing"))
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    fake_registry = types.SimpleNamespace(
        HKEY_CLASSES_ROOT=object(),
        QueryValue=lambda *_args: (_ for _ in ()).throw(FileNotFoundError()),
    )
    monkeypatch.setitem(sys.modules, "winreg", fake_registry)
    with pytest.raises(smoke.SmokeFailure, match="registration") as exc:
        smoke.discover()
    assert exc.value.code == "grapher_not_installed"

    exe = ROOT / "missing" / "Golden Software" / "Grapher" / "Grapher.exe"
    monkeypatch.setattr(Path, "is_file", lambda self: self == exe)
    with pytest.raises(smoke.SmokeFailure) as exc:
        smoke.discover()
    assert exc.value.code == "grapher_com_class_not_registered"


def test_discovery_uses_registered_executable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(smoke.platform, "system", lambda: "Windows")
    exe = tmp_path / "Golden Software" / "Grapher" / "Grapher.exe"
    exe.parent.mkdir(parents=True)
    exe.touch()
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    clsid = "{test-clsid}"
    values = {
        smoke.PROGID + r"\CLSID": clsid,
        rf"CLSID\{clsid}\LocalServer32": f'"{exe}" /Automation',
    }
    monkeypatch.setitem(sys.modules, "winreg", types.SimpleNamespace(
        HKEY_CLASSES_ROOT=object(), QueryValue=lambda _root, key: values[key],
    ))
    assert smoke.discover()["executable"] == str(exe)


def test_failed_smoke_emits_structured_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail() -> None:
        raise smoke.SmokeFailure("grapher_com_class_not_registered", "COM class missing")

    monkeypatch.setattr(smoke, "discover", fail)
    assert smoke.main([]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report == {
        "status": "failed",
        "engine": "grapher",
        "error": {"code": "grapher_com_class_not_registered", "message": "COM class missing"},
    }


def test_activation_error_is_normalized(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(smoke, "discover", lambda: {"progid": smoke.PROGID})
    monkeypatch.setattr(smoke, "grapher_pids", lambda: set())
    fake_com = types.SimpleNamespace(CoInitialize=lambda: None, CoUninitialize=lambda: None)
    monkeypatch.setitem(sys.modules, "pythoncom", fake_com)
    fake_client = types.SimpleNamespace(
        DispatchEx=lambda _progid: (_ for _ in ()).throw(RuntimeError("COM unavailable"))
    )
    monkeypatch.setitem(sys.modules, "win32com.client", fake_client)
    result = smoke.run_smoke(tmp_path)
    assert result["status"] == "failed"
    assert result["error"]["code"] == "grapher_com_activation_failed"
    assert json.loads(Path(result["report_path"]).read_text(encoding="utf-8")) == result


def test_cleanup_warns_without_terminating_unattributed_pid_after_com_quit_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = {42}
    monkeypatch.setattr(smoke, "grapher_pids", lambda: set(running))
    monkeypatch.setattr(
        smoke, "call", lambda *_args: (_ for _ in ()).throw(RuntimeError("RPC unavailable"))
    )

    monkeypatch.setattr(smoke.os, "kill", lambda *_args: pytest.fail("must not kill a PID"))

    warning = smoke.quit_owned_application(object(), 42)
    assert warning is not None and "RPC unavailable" in warning


def test_cli_routes_grapher_smoke_without_origin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "bootstrap_engine", lambda _value: ROOT / "runtime")
    monkeypatch.setattr(smoke, "run_smoke", lambda *_args, **_kwargs: {"status": "ok", "engine": "grapher"})
    assert cli.main(["grapher-smoke", "--hidden"]) == 0
    assert json.loads(capsys.readouterr().out)["engine"] == "grapher"


@pytest.mark.skipif(os.name != "nt", reason="Grapher COM requires Windows")
@pytest.mark.grapher
def test_real_grapher_smoke(tmp_path: Path) -> None:
    pytest.importorskip("pythoncom")
    try:
        smoke.discover()
    except smoke.SmokeFailure as exc:
        pytest.skip(str(exc))
    completed = subprocess.run(  # noqa: S603 - fixed local CLI and test-created output
        [
            sys.executable,
            str(ROOT / "skill" / "figureloom" / "scripts" / "figureloom.py"),
            "grapher-smoke",
            "--output-dir",
            str(tmp_path / "中文"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "ok", result.get("error")
    assert result["readback"]["document_opened"] is True
    assert result["readback"]["graph_count"] >= 1
    assert result["readback"]["plot_count"] >= 1
    assert result["readback"]["axis_count"] >= 2
    assert {"x": 1, "y": 2} in result["readback"]["columns"]
    for name, signature in (("grf", b"Grapher"), ("png", b"\x89PNG"), ("pdf", b"%PDF")):
        assert Path(result["artifacts"][name]).read_bytes().startswith(signature)
    assert json.loads(Path(result["report_path"]).read_text(encoding="utf-8")) == result
    assert result["application"]["pid"] not in smoke.grapher_pids()
