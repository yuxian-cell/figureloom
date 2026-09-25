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
@pytest.mark.parametrize(
    ("template_id", "y_columns"),
    [
        ("scatter", ("Y",)),
        ("trend", ("Control",)),
        ("trend", ("Control", "Treatment")),
    ],
)
def test_real_xy_render_plan_to_grapher_round_trip(
    tmp_path: Path, template_id: str, y_columns: tuple[str, ...]
) -> None:
    pytest.importorskip("pythoncom")
    try:
        discover()
    except SmokeFailure as exc:
        pytest.skip(str(exc))
    source = tmp_path / "实验数据.csv"
    source.write_text(
        ",".join(("X", *y_columns))
        + "\n"
        + "\n".join(
            ",".join(str((row + 1) * (column + 1)) for column in range(len(y_columns) + 1))
            for row in range(5)
        )
        + "\n",
        encoding="utf-8",
    )
    mapping = {"assignments": {"X": "x", **dict.fromkeys(y_columns, "series")}}
    understanding = core.understand_data(
        source, template_id=template_id, mapping=mapping, engine_home=ROOT / "runtime"
    )
    confirmation = understanding["confirmation_gate"]["confirmation_payload_template"]
    plan = core.build_plan(
        source,
        template_id=template_id,
        claim="Y increases with X.",
        evidence_role="relationship" if template_id == "scatter" else "trend",
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
    assert report["checks"]["line_symbol_mode"] is True
    assert report["checks"]["legend_labels"] is True
    assert report["checks"]["graph_title"] is True
    assert report["readback"]["graph_title"] == "Y increases with X."
    assert report["readback"]["series_count"] == len(y_columns)
    assert [plot["type"] for plot in report["readback"]["plots"]] == [
        "xy_scatter" if template_id == "scatter" else "xy_line"
    ] * len(y_columns)
    assert report["readback"]["plots"][0]["x_column"] == "X"
    assert [plot["y_column"] for plot in report["readback"]["plots"]] == list(y_columns)
    if len(y_columns) > 1:
        assert report["readback"]["legends"][0]["entries"] == list(y_columns)


@pytest.mark.grapher
@pytest.mark.skipif(os.name != "nt", reason="Grapher COM requires Windows")
@pytest.mark.parametrize(
    ("fixture", "template_id", "y_errors"),
    [
        ("line_single.csv", "line_error", {"Control": "Control_SD"}),
        (
            "line_multi.csv",
            "line_error",
            {"Control": "Control_SD", "Treatment": "Treatment_SD"},
        ),
        ("line_single.csv", "scatter", {"Control": "Control_SD"}),
    ],
)
def test_real_symmetric_y_error_round_trip(
    tmp_path: Path, fixture: str, template_id: str, y_errors: dict[str, str]
) -> None:
    pytest.importorskip("pythoncom")
    try:
        discover()
    except SmokeFailure as exc:
        pytest.skip(str(exc))
    source = tmp_path / "实验误差.csv"
    source.write_bytes((ROOT / "tests/fixtures/grapher_error" / fixture).read_bytes())
    columns = source.read_text(encoding="utf-8").splitlines()[0].split(",")
    mapping = {
        "assignments": {
            column: "x" if column == "Time" else "error" if column.endswith("_SD") else "series"
            for column in columns
        }
    }
    proposal = core.understand_data(
        source, template_id=template_id, mapping=mapping, engine_home=ROOT / "runtime"
    )
    plan = core.build_plan(
        source,
        template_id=template_id,
        claim="Values increase with time.",
        evidence_role="trend",
        mapping=mapping,
        semantic_confirmation=proposal["confirmation_gate"]["confirmation_payload_template"],
        engine_home=ROOT / "runtime",
    )
    plan_file = tmp_path / "render-plan.json"
    plan_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    output = tmp_path / "result"
    cli = ROOT / "skill/editaplot/scripts/editaplot.py"
    rendered = subprocess.run(
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
    report = json.loads(
        (Path(result["output_dir"]) / "grapher_verify_report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "ok"
    assert report["checks"]["error_bindings"] is True
    assert {plot["y_column"]: plot["error"]["column"] for plot in report["readback"]["plots"]} == y_errors
    assert all(
        plot["error"]["direction"] == "y" and plot["error"]["symmetric"]
        for plot in report["readback"]["plots"]
    )
    assert Path(result["editable"]).read_bytes().startswith(b"Grapher")
    assert Path(result["exports"]["png"]).read_bytes().startswith(b"\x89PNG")
    assert Path(result["exports"]["pdf"]).read_bytes().startswith(b"%PDF")
