#!/usr/bin/env python
"""Command-line entry point used by the EditaPlot Codex Skill."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path
from typing import Any

from editaplot_core import (
    EditaPlotError,
    bootstrap_engine,
    build_medical_panel_plan,
    build_origin_smoke_command,
    build_plan,
    catalog,
    doctor,
    inspect_data,
    inspect_reference,
    load_json,
    palette_catalog,
    recommend_charts,
    repair_environment,
    review_reference_figure,
    start_session,
    understand_data,
    write_json,
)


def _engine_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--engine-home",
        help="Source engine root; defaults to EDITAPLOT_ENGINE_HOME or local discovery.",
    )


def _backend_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--engine", default="origin", help="Rendering engine: origin or grapher.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EditaPlot")
    parser.add_argument("--version", action="version", version=f"EditaPlot {_version()}")
    parser.add_argument("--verbose", action="store_true", help="Save native exception details to runtime.log")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Check local analysis/render prerequisites")
    doctor_parser.add_argument(
        "--repair",
        action="store_true",
        help="Create a project-local environment and install audited Python dependencies only.",
    )
    _engine_option(doctor_parser)
    _backend_option(doctor_parser)
    doctor_parser.add_argument(
        "--live", action="store_true", help="Activate and close a fresh native instance"
    )
    doctor_parser.add_argument("--human", action="store_true", help="Print a concise readable diagnosis")

    repair_parser = subparsers.add_parser(
        "repair-environment",
        help=argparse.SUPPRESS,
    )
    _engine_option(repair_parser)

    catalog_parser = subparsers.add_parser("catalog", help="List verified public Origin routes")
    _engine_option(catalog_parser)

    palettes_parser = subparsers.add_parser("palettes", help="List Chinese-first scientific palettes")
    palettes_parser.add_argument("--all", action="store_true", help="Include advanced palettes")
    _engine_option(palettes_parser)

    inspect_parser = subparsers.add_parser("inspect", help="Profile a table without modifying it")
    inspect_parser.add_argument("input_file")
    inspect_parser.add_argument("--output")
    _engine_option(inspect_parser)

    start_parser = subparsers.add_parser(
        "start",
        help="Open a read-only beginner session and ask for scientific confirmation",
    )
    start_parser.add_argument("input_file")
    start_parser.add_argument("--intent", default="")
    start_parser.add_argument("--limit", type=int, default=3)
    start_parser.add_argument("--output")
    _engine_option(start_parser)

    recommend_parser = subparsers.add_parser("recommend", help="Rank suitable verified templates")
    recommend_parser.add_argument("input_file")
    recommend_parser.add_argument("--intent", default="")
    recommend_parser.add_argument("--limit", type=int, default=3)
    recommend_parser.add_argument("--output")
    _engine_option(recommend_parser)

    reference_inspect_parser = subparsers.add_parser(
        "reference-inspect",
        help="Validate a local reference image without OCR or rendering",
    )
    reference_inspect_parser.add_argument("reference_image")
    reference_inspect_parser.add_argument("--output")
    _engine_option(reference_inspect_parser)

    reference_review_parser = subparsers.add_parser(
        "reference-review",
        help="Validate a declarative reference-figure grammar and request confirmation",
    )
    reference_review_parser.add_argument("reference_image")
    reference_review_parser.add_argument("reference_spec_json")
    reference_review_parser.add_argument("--output")
    _engine_option(reference_review_parser)

    understand_parser = subparsers.add_parser(
        "understand",
        help="Explain every source column and proposed figure element before planning",
    )
    understand_parser.add_argument("input_file")
    understand_parser.add_argument("--template-id", required=True)
    understand_parser.add_argument("--mapping-json", help="Confirmed assignments/context JSON")
    understand_parser.add_argument("--output")
    _engine_option(understand_parser)

    plan_parser = subparsers.add_parser("plan", help="Freeze a selected template and figure contract")
    plan_parser.add_argument("input_file")
    plan_parser.add_argument("--template-id", required=True)
    plan_parser.add_argument("--claim", required=True)
    plan_parser.add_argument("--evidence-role", default="comparison")
    plan_parser.add_argument("--intent", default="")
    plan_parser.add_argument("--x-title")
    plan_parser.add_argument("--y-title")
    plan_parser.add_argument("--palette-id", help="Freeze a compatible palette from `palettes`")
    plan_parser.add_argument(
        "--visual-style-json",
        help="Confirmed exact XPS visual fields (colors, pt width, transparency, page, legend)",
    )
    plan_parser.add_argument(
        "--target-output",
        default="editable Origin figure and publication exports",
    )
    plan_parser.add_argument("--mapping-json", help="Confirmed assignments/context JSON")
    plan_parser.add_argument("--fit-spec-json", help="Optional backend-neutral FitSpec JSON file")
    plan_parser.add_argument(
        "--semantic-confirmation-json",
        required=True,
        help="Explicit confirmation bound to the latest `understand` proposal hash",
    )
    plan_parser.add_argument("--reference-image")
    plan_parser.add_argument("--reference-spec-json")
    plan_parser.add_argument("--reference-confirmation-json")
    plan_parser.add_argument(
        "--reference-route",
        choices=("template_adaptation", "controlled_composition"),
        default="template_adaptation",
    )
    plan_parser.add_argument("--reference-bindings-json")
    plan_parser.add_argument("--output", required=True)
    _engine_option(plan_parser)

    render_parser = subparsers.add_parser(
        "render",
        help="Execute an approved render plan through the selected native application",
    )
    render_parser.add_argument("plan_file")
    render_parser.add_argument("--python", dest="python_executable")
    render_parser.add_argument("--output-dir")
    render_parser.add_argument("--close-origin", action="store_true")
    _engine_option(render_parser)
    _backend_option(render_parser)

    generic_smoke_parser = subparsers.add_parser(
        "smoke", help="Run the selected engine's native automation smoke test"
    )
    generic_smoke_parser.add_argument("--output-dir", required=True)
    generic_smoke_parser.add_argument("--python", dest="python_executable")
    generic_smoke_parser.add_argument("--hidden", action="store_true")
    generic_smoke_parser.add_argument("--keep-application-open", action="store_true")
    _engine_option(generic_smoke_parser)
    _backend_option(generic_smoke_parser)

    smoke_parser = subparsers.add_parser(
        "origin-smoke",
        help="Test an EditaPlot-owned Origin instance and the full minimal export loop",
    )
    smoke_parser.add_argument("--output-dir", required=True)
    smoke_parser.add_argument("--python", dest="python_executable")
    smoke_parser.add_argument("--keep-origin-open", action="store_true")
    _engine_option(smoke_parser)

    grapher_smoke_parser = subparsers.add_parser(
        "grapher-smoke",
        help="Test native Grapher plot, GRF save, export, reopen, and object readback",
    )
    grapher_smoke_parser.add_argument("--output-dir")
    grapher_smoke_parser.add_argument("--hidden", action="store_true")
    _engine_option(grapher_smoke_parser)

    verify_parser = subparsers.add_parser("verify", help="Check required engine artifacts")
    verify_parser.add_argument("output_directory")
    verify_parser.add_argument("--output")
    _engine_option(verify_parser)
    _backend_option(verify_parser)

    workflow_preview = subparsers.add_parser(
        "workflow-preview", help="Inspect, recommend, and prepare confirmation"
    )
    workflow_preview.add_argument("input_file")
    workflow_preview.add_argument("--output-dir", required=True)
    workflow_preview.add_argument("--template-id")
    workflow_preview.add_argument("--sheet")
    workflow_preview.add_argument("--intent", default="")
    workflow_preview.add_argument("--mapping-json")
    workflow_preview.add_argument("--fit-spec-json")
    _engine_option(workflow_preview)
    _backend_option(workflow_preview)

    workflow_render = subparsers.add_parser("workflow-render", help="Confirm and render a workflow preview")
    workflow_render.add_argument("preview_file")
    workflow_render.add_argument("--claim", required=True)
    workflow_render.add_argument("--confirm", action="store_true", required=True)
    workflow_render.add_argument("--human", action="store_true", help="Show result paths and verification")

    edit_parser = subparsers.add_parser("edit", help="Modify a saved native project from its session")
    edit_parser.add_argument("session_file")
    edit_parser.add_argument("request", nargs="?")
    edit_parser.add_argument("--edit-json")
    edit_parser.add_argument("--human", action="store_true", help="Show edited project and verification")

    panel_parser = subparsers.add_parser(
        "panel-plan",
        help="Freeze a deidentification-aware medical multi-panel layout plan",
    )
    panel_parser.add_argument("config_file")
    panel_parser.add_argument("--claim", required=True)
    panel_parser.add_argument("--title", default="Medical imaging & AI evidence")
    panel_parser.add_argument("--output", required=True)
    return parser


def _emit(payload: dict[str, Any], output: str | None = None) -> None:
    if output:
        write_json(output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)


def _version() -> str:
    try:
        return metadata.version("editaplot-runtime")
    except metadata.PackageNotFoundError:
        project = Path(__file__).resolve().parents[3] / "runtime" / "pyproject.toml"
        match = re.search(r'^version\s*=\s*"([^"]+)"', project.read_text(encoding="utf-8"), re.M)
        return match.group(1) if match else "unknown"


def _native_pids(engine: str) -> set[int]:
    name = "Origin64.exe" if engine == "origin" else "Grapher.exe"
    tasklist = shutil.which("tasklist")
    if tasklist is None:
        return set()
    result = subprocess.run(  # noqa: S603 - fixed Windows system utility
        [tasklist, "/FO", "CSV", "/NH"], capture_output=True, text=True, check=False
    )
    return {int(row[1]) for row in csv.reader(result.stdout.splitlines())
            if len(row) > 1 and row[0].casefold() == name.casefold()}


def _live_doctor(engine: str) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(root / "runtime" / "src"), str(root / "skill" / "editaplot" / "scripts"),
         environment.get("PYTHONPATH", "")))
    before = _native_pids(engine)
    try:
        process = subprocess.run(  # noqa: S603 - fixed local module, no shell
            [sys.executable, "-m", "editaplot_engine.doctor_probe", engine],
            cwd=root, env=environment, capture_output=True, text=True,
            errors="replace", timeout=120, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"automation": "failed", "error": {"code": f"{engine}_unavailable",
                "message": f"Native activation probe could not complete: {type(exc).__name__}"}}
    lines = process.stdout.splitlines()
    try:
        result = next(json.loads(line) for line in reversed(lines) if line.startswith("{"))
    except (StopIteration, ValueError):
        result = {"automation": "failed", "error": {"code": f"{engine}_unavailable",
                  "message": "Native activation probe returned no valid report."}}
    remaining = _native_pids(engine) - before
    result["existing_native_processes"] = len(before)
    result["shutdown"] = "unknown_process_remaining" if remaining else "clean_shutdown"
    if before:
        result["warning"] = (
            f"{len(before)} {engine} process(es) were already open; ownership is unknown. "
            "They were not closed."
        )
    if remaining:
        result["warning"] = (
            result.get("warning", "") +
            " A newly observed native process remains; close stale automation sessions "
            "manually if later jobs fail."
        )
    if process.returncode and result["automation"] == "ok":
        result["automation"] = "failed"
    return result


def _human_doctor(report: dict[str, Any]) -> None:
    print(f"Engine: {report.get('engine', 'origin')}")
    print(f"Installed: {'yes' if report.get('ready_for_render') else 'no or prerequisites missing'}")
    live = report.get("live_probe")
    if live:
        print(f"Automation: {live['automation']}")
        print(f"Version: {live.get('version', report.get('version', 'unknown'))}")
        print(f"Shutdown: {live.get('shutdown', 'not checked')}")
        if live.get("warning"):
            print(f"Warning: {live['warning']}")
        if live.get("error"):
            print(f"Error: {live['error']['message']}")
    else:
        print("Automation: not tested (run with --live)")


def _human_session(session: dict[str, Any], session_file: Path) -> None:
    artifacts = session["artifacts"]
    print(f"Engine: {session['engine']}")
    print(f"Project: {artifacts['editable']}")
    for name, path in artifacts["exports"].items():
        print(f"{name.upper()}: {path}")
    print(f"Verified: {'yes' if session['verification']['status'] == 'ok' else 'no'}")
    print(f"Session: {session_file}")


def _paths_refer_to_same_file(left: str | Path, right: str | Path) -> bool:
    left_path = Path(left).expanduser()
    right_path = Path(right).expanduser()
    try:
        if left_path.resolve() == right_path.resolve():
            return True
        if left_path.exists() and right_path.exists():
            return os.path.samefile(left_path, right_path)
    except OSError:
        return False
    return False


def _ensure_output_does_not_replace_paths(
    output: str | None,
    protected_paths: list[str | Path],
    *,
    code: str,
    message: str,
) -> None:
    if not output:
        return
    conflict = next(
        (path for path in protected_paths if _paths_refer_to_same_file(path, output)),
        None,
    )
    if conflict is not None:
        raise EditaPlotError(
            code,
            message,
            protected_path=str(Path(conflict).expanduser().resolve()),
        )


def _ensure_output_does_not_replace_input(
    input_path: str | None,
    output: str | None,
) -> None:
    if not input_path:
        return
    _ensure_output_does_not_replace_paths(
        output,
        [input_path],
        code="source_output_conflict",
        message="A JSON output cannot replace the command's input file.",
    )


def _ensure_verify_output_does_not_replace_artifact(
    output_directory: str,
    output: str | None,
) -> None:
    directory = Path(output_directory).expanduser()
    required = [
        directory / name
        for name in (
            "result.png",
            "result.pdf",
            "result.tif",
            "result.opju",
            "result.grf",
            "origin_verify_report.json",
            "grapher_verify_report.json",
            "validation_report.json",
        )
    ]
    _ensure_output_does_not_replace_paths(
        output,
        required,
        code="verification_artifact_output_conflict",
        message="A verification JSON output cannot replace a required Origin artifact.",
    )


def _start_worker_process(
    command: list[str],
    *,
    engine_root: Path,
    environment: dict[str, str],
    label: str,
) -> subprocess.Popen[str]:
    """Start a fixed local worker and normalize Windows launch failures."""

    try:
        return subprocess.Popen(  # noqa: S603 - fixed module invocation, never shell=True
            command,
            cwd=str(engine_root),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except PermissionError as exc:
        raise EditaPlotError(
            "worker_start_permission_denied",
            f"Windows blocked the {label} process. Allow this EditaPlot project and its selected "
            "Python executable in the current user session, then retry; administrator, DCOM, "
            "registry, and firewall changes are not required.",
            os_error=type(exc).__name__,
            errno=exc.errno,
        ) from exc
    except OSError as exc:
        raise EditaPlotError(
            "worker_start_failed",
            f"EditaPlot could not start the {label} process. Re-run editaplot.cmd --diagnose "
            "and check whether the selected Python path still exists.",
            os_error=type(exc).__name__,
            errno=exc.errno,
        ) from exc


def _run_render(args: argparse.Namespace) -> int:
    plan = load_json(args.plan_file)
    engine = _selected_engine(args)
    result = engine.render(
        plan,
        plan_file=args.plan_file,
        engine_home=args.engine_home,
        python_executable=args.python_executable,
        output_dir=args.output_dir,
        close_application=args.close_origin,
    )
    if engine.name != "origin" or plan.get("fit") is not None:
        _emit(result.to_dict())
    return 0


def _selected_engine(args: argparse.Namespace) -> Any:
    bootstrap_engine(getattr(args, "engine_home", None))
    from editaplot_engine import get_engine

    return get_engine(getattr(args, "engine", "origin"))


def _run_smoke(args: argparse.Namespace) -> int:
    engine = _selected_engine(args)
    report = engine.smoke(
        args.output_dir,
        engine_home=args.engine_home,
        python_executable=args.python_executable,
        visible=not args.hidden,
        keep_application_open=args.keep_application_open,
    )
    if engine.name != "origin":
        _emit(report)
    return 0 if report.get("status") not in {"failed", "error"} else 2


def _run_origin_smoke(args: argparse.Namespace) -> int:
    command, env, engine_root = build_origin_smoke_command(
        output_dir=args.output_dir,
        engine_home=args.engine_home,
        python_executable=args.python_executable,
        keep_origin_open=args.keep_origin_open,
    )
    print(
        json.dumps(
            {
                "type": "editaplot_origin_smoke_start",
                "engine_home": str(engine_root),
                "connection_mode": "new_isolated",
                "output_dir": str(Path(args.output_dir).expanduser().resolve()),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    process = _start_worker_process(
        command,
        engine_root=engine_root,
        environment=env,
        label="Origin smoke worker",
    )
    stdout = process.stdout
    if stdout is None:
        process.kill()
        raise EditaPlotError(
            "worker_pipe_missing",
            "Could not read the Origin smoke worker output stream.",
        )
    for line in stdout:
        print(line.rstrip("\r\n"), flush=True)
    return int(process.wait())


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.verbose:
        os.environ["EDITAPLOT_VERBOSE"] = "1"
    try:
        if args.command == "doctor":
            before = (
                doctor(engine_home=args.engine_home)
                if args.engine == "origin"
                else _selected_engine(args).doctor(engine_home=args.engine_home)
            )
            if args.live:
                before["live_probe"] = (
                    _live_doctor(args.engine) if before["ready_for_render"]
                    else {"automation": "not_run", "reason": "Static prerequisites are missing."}
                )
                try:
                    with tempfile.NamedTemporaryFile(dir=Path.cwd()) as _probe:
                        before["workspace_writable"] = True
                except OSError:
                    before["workspace_writable"] = False
            if args.repair and not before["ready_for_render"]:
                if args.engine != "origin":
                    raise EditaPlotError(
                        "automatic_repair_unavailable",
                        "Automatic dependency repair is currently available only for Origin.",
                    )
                if before["automatic_repair"]["available"]:
                    _emit(
                        {
                            "schema_version": "1.0",
                            "ok": True,
                            "before": before,
                            "repair": repair_environment(engine_home=args.engine_home),
                        }
                    )
                elif before["missing_python_dependencies"]:
                    raise EditaPlotError(
                        "automatic_repair_unavailable",
                        "Project-local dependency repair is unavailable for the reported blockers.",
                        manual_blockers=before["manual_blockers"],
                        supported_python=before["automatic_repair"]["supported_python"],
                    )
                else:
                    _human_doctor(before) if args.human else _emit(before)
            else:
                _human_doctor(before) if args.human else _emit(before)
            if args.live and (
                before["live_probe"]["automation"] != "ok"
                or not before["workspace_writable"]
            ):
                return 2
        elif args.command == "repair-environment":
            _emit(repair_environment(engine_home=args.engine_home))
        elif args.command == "catalog":
            _emit(catalog(engine_home=args.engine_home))
        elif args.command == "palettes":
            _emit(
                palette_catalog(
                    engine_home=args.engine_home,
                    public_only=not args.all,
                )
            )
        elif args.command == "inspect":
            _ensure_output_does_not_replace_input(args.input_file, args.output)
            _emit(
                inspect_data(args.input_file, engine_home=args.engine_home),
                args.output,
            )
        elif args.command == "start":
            _ensure_output_does_not_replace_input(args.input_file, args.output)
            _emit(
                start_session(
                    args.input_file,
                    intent=args.intent,
                    engine_home=args.engine_home,
                    limit=args.limit,
                ),
                args.output,
            )
        elif args.command == "recommend":
            _ensure_output_does_not_replace_input(args.input_file, args.output)
            _emit(
                recommend_charts(
                    args.input_file,
                    intent=args.intent,
                    engine_home=args.engine_home,
                    limit=args.limit,
                ),
                args.output,
            )
        elif args.command == "reference-inspect":
            _ensure_output_does_not_replace_input(args.reference_image, args.output)
            _emit(
                inspect_reference(
                    args.reference_image,
                    engine_home=args.engine_home,
                ),
                args.output,
            )
        elif args.command == "reference-review":
            _ensure_output_does_not_replace_input(args.reference_image, args.output)
            _ensure_output_does_not_replace_input(args.reference_spec_json, args.output)
            _emit(
                review_reference_figure(
                    args.reference_image,
                    load_json(args.reference_spec_json),
                    engine_home=args.engine_home,
                ),
                args.output,
            )
        elif args.command == "understand":
            _ensure_output_does_not_replace_input(args.input_file, args.output)
            _ensure_output_does_not_replace_input(args.mapping_json, args.output)
            mapping = load_json(args.mapping_json) if args.mapping_json else None
            _emit(
                understand_data(
                    args.input_file,
                    template_id=args.template_id,
                    mapping=mapping,
                    engine_home=args.engine_home,
                ),
                args.output,
            )
        elif args.command == "plan":
            _ensure_output_does_not_replace_input(args.input_file, args.output)
            _ensure_output_does_not_replace_input(args.mapping_json, args.output)
            _ensure_output_does_not_replace_input(args.visual_style_json, args.output)
            _ensure_output_does_not_replace_input(
                args.semantic_confirmation_json,
                args.output,
            )
            for reference_input in (
                args.reference_image,
                args.reference_spec_json,
                args.reference_confirmation_json,
                args.reference_bindings_json,
                args.fit_spec_json,
            ):
                _ensure_output_does_not_replace_input(reference_input, args.output)
            mapping = load_json(args.mapping_json) if args.mapping_json else None
            fit_spec = load_json(args.fit_spec_json) if args.fit_spec_json else None
            visual_style = load_json(args.visual_style_json) if args.visual_style_json else None
            semantic_confirmation = load_json(args.semantic_confirmation_json)
            reference_spec = (
                load_json(args.reference_spec_json)
                if args.reference_spec_json
                else None
            )
            reference_confirmation = (
                load_json(args.reference_confirmation_json)
                if args.reference_confirmation_json
                else None
            )
            reference_bindings = (
                load_json(args.reference_bindings_json)
                if args.reference_bindings_json
                else None
            )
            payload = build_plan(
                args.input_file,
                template_id=args.template_id,
                claim=args.claim,
                evidence_role=args.evidence_role,
                target_output=args.target_output,
                intent=args.intent,
                x_title=args.x_title,
                y_title=args.y_title,
                palette_id=args.palette_id,
                visual_style=visual_style,
                mapping=mapping,
                semantic_confirmation=semantic_confirmation,
                reference_image=args.reference_image,
                reference_spec=reference_spec,
                reference_confirmation=reference_confirmation,
                reference_route=args.reference_route,
                reference_bindings=reference_bindings,
                engine_home=args.engine_home,
                fit_spec=fit_spec,
            )
            _emit(payload, args.output)
        elif args.command == "render":
            return _run_render(args)
        elif args.command == "smoke":
            return _run_smoke(args)
        elif args.command == "origin-smoke":
            return _run_origin_smoke(args)
        elif args.command == "grapher-smoke":
            bootstrap_engine(args.engine_home)
            from grapher_sciplot.smoke import run_smoke

            report = run_smoke(
                Path(args.output_dir) if args.output_dir else None,
                visible=not args.hidden,
            )
            _emit(report)
            return 0 if report["status"] == "ok" else 2
        elif args.command == "verify":
            _ensure_verify_output_does_not_replace_artifact(args.output_directory, args.output)
            report = _selected_engine(args).verify(args.output_directory)
            _emit(report, args.output)
            if args.engine != "origin" and report.get("status") == "failed":
                return 2
        elif args.command == "workflow-preview":
            bootstrap_engine(args.engine_home)
            from editaplot_engine.workflow import preview

            _emit(preview(
                args.input_file, args.output_dir, engine_name=args.engine,
                template_id=args.template_id, sheet=args.sheet, intent=args.intent,
                mapping=load_json(args.mapping_json) if args.mapping_json else None,
                fit_spec=load_json(args.fit_spec_json) if args.fit_spec_json else None,
                engine_home=args.engine_home,
            ))
        elif args.command == "workflow-render":
            bootstrap_engine(None)
            from editaplot_engine.workflow import render_confirmed

            if args.human:
                os.environ["EDITAPLOT_HUMAN"] = "1"
            session = render_confirmed(args.preview_file, claim=args.claim, confirmed=args.confirm)
            if args.human:
                _human_session(session, Path(args.preview_file).resolve().parent / "session.json")
            else:
                _emit(session)
        elif args.command == "edit":
            bootstrap_engine(None)
            from editaplot_engine.workflow import edit_session, normalize_edit, parse_edit_phrase

            if bool(args.request) == bool(args.edit_json):
                raise EditaPlotError("edit_request_required", "Provide a phrase or --edit-json, not both.")
            if args.edit_json:
                raw = load_json(args.edit_json)
                edit = normalize_edit(raw.get("operation", ""), value=raw.get("value", ""),
                                      axis=raw.get("axis"), series=raw.get("series"))
            else:
                edit = parse_edit_phrase(args.request)
            outcome = edit_session(args.session_file, edit, request=args.request or "structured EditPlan")
            if args.human:
                session_path = Path(outcome["session"])
                _human_session(json.loads(session_path.read_text(encoding="utf-8")), session_path)
            else:
                _emit(outcome)
        elif args.command == "panel-plan":
            _ensure_output_does_not_replace_input(args.config_file, args.output)
            _emit(
                build_medical_panel_plan(
                    args.config_file,
                    claim=args.claim,
                    title=args.title,
                ),
                args.output,
            )
        else:  # pragma: no cover - argparse enforces a command
            raise EditaPlotError("command_unknown", f"Unknown command: {args.command}")
        return 0
    except EditaPlotError as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr, flush=True)
        return 2
    except Exception as exc:
        to_dict = getattr(exc, "to_dict", None)
        if callable(to_dict) and hasattr(exc, "engine"):
            print(json.dumps(to_dict(), ensure_ascii=False, indent=2), file=sys.stderr, flush=True)
            return int(getattr(exc, "exit_code", 2))
        raise
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "error": {"code": "cancelled"}}), file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
