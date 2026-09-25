from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "skill" / "editaplot" / "scripts", ROOT / "runtime" / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import editaplot_core as core  # noqa: E402
from grapher_sciplot.smoke import SmokeFailure, discover  # noqa: E402


@pytest.mark.grapher
@pytest.mark.skipif(os.name != "nt", reason="Grapher COM requires Windows")
def test_real_render_plan_to_grapher_round_trip(tmp_path: Path) -> None:
    pytest.importorskip("pythoncom")
    try:
        discover()
    except SmokeFailure as exc:
        pytest.skip(str(exc))
    source = tmp_path / "实验数据.csv"
    source.write_text("X,Y\n1,1\n2,4\n3,9\n4,16\n5,25\n", encoding="utf-8")
    mapping = {"assignments": {"X": "x", "Y": "series"}, "plot_mode": "scatter"}
    understanding = core.understand_data(
        source, template_id="scatter", mapping=mapping, engine_home=ROOT / "runtime"
    )
    confirmation = understanding["confirmation_gate"]["confirmation_payload_template"]
    plan = core.build_plan(
        source,
        template_id="scatter",
        claim="Y increases with X.",
        evidence_role="relationship",
        mapping=mapping,
        semantic_confirmation=confirmation,
        engine_home=ROOT / "runtime",
    )
    plan_file = tmp_path / "render-plan.json"
    plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    cli = ROOT / "skill" / "editaplot" / "scripts" / "editaplot.py"
    output = tmp_path / "result"
    rendered = subprocess.run(  # noqa: S603 - fixed local CLI and source-created plan
        [
            sys.executable,
            str(cli),
            "render",
            str(plan_file),
            "--engine",
            "grapher",
            "--output-dir",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    assert rendered.returncode == 0, rendered.stderr
    result = json.loads(rendered.stdout)
    verified = subprocess.run(  # noqa: S603 - fixed local CLI and source-created output
        [sys.executable, str(cli), "verify", str(output), "--engine", "grapher"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    assert verified.returncode == 0, verified.stderr
    report = json.loads(verified.stdout)

    assert Path(result["editable"]).read_bytes().startswith(b"Grapher")
    assert Path(result["exports"]["png"]).read_bytes().startswith(b"\x89PNG")
    assert Path(result["exports"]["pdf"]).read_bytes().startswith(b"%PDF")
    assert report["status"] == "ok"
    assert report["checks"]["document_reopened"] is True
    assert report["readback"]["plots"][0]["x_column"] == "X"
    assert report["readback"]["plots"][0]["y_column"] == "Y"
