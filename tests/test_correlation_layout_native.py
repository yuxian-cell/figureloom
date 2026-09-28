"""Phase 17 local real-data acceptance: A/B/C through both native backends."""

import csv
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "runtime/src", ROOT / "skill/figureloom/scripts", ROOT / "tests"):
    sys.path.insert(0, str(path))

from figureloom_engine.correlation_heatmap import CorrelationHeatmapSpec, verify_readback  # noqa: E402
from figureloom_engine.correlation_layout import plan_layout, verify_layout  # noqa: E402
from figureloom_engine.workflow import preview, render_confirmed  # noqa: E402
from test_correlation_layout import concrete  # noqa: E402


@pytest.mark.parametrize(
    "engine",
    [pytest.param("origin", marks=pytest.mark.origin), pytest.param("grapher", marks=pytest.mark.grapher)],
)
@pytest.mark.parametrize("case", ["matrix", "pvalues", "raw"])
def test_concrete_native_layout(tmp_path, engine, case):
    spec = concrete(pvalues=case != "matrix")
    sources = [
        ROOT / "tests/fixtures/correlation_heatmap/concrete_correlation.csv",
        ROOT / "tests/fixtures/correlation_heatmap/concrete_pvalues.csv",
    ]
    if case == "raw":
        source = Path(os.environ.get("FIGURELOOM_CONCRETE_RAW", "concrete_raw.csv"))
        if not source.is_file():
            pytest.skip("Local UCI Concrete raw acceptance source not provided")
        sources.append(source)
        scipy = pytest.importorskip("scipy.stats")
        import numpy as np

        with source.open(encoding="utf-8-sig", newline="") as stream:
            records = list(csv.reader(stream))
        assert tuple(records[0]) == spec.labels
        values = np.asarray([[float(v) for v in row] for row in records[1:]])
        assert values.shape == (1030, 9) and np.isfinite(values).all()
        matrix, probabilities = np.eye(9), np.zeros((9, 9))
        for i in range(9):
            for j in range(i):
                result = scipy.pearsonr(values[:, i], values[:, j], alternative="two-sided")
                matrix[i, j] = matrix[j, i] = result.statistic
                probabilities[i, j] = probabilities[j, i] = result.pvalue
        assert np.allclose(matrix, spec.correlation_matrix, atol=1e-13, rtol=0)
        assert np.allclose(probabilities, spec.p_value_matrix, atol=1e-13, rtol=0)
        spec = CorrelationHeatmapSpec(
            spec.labels, matrix.tolist(), probabilities.tolist(), significance_enabled=True, title=spec.title
        )
        (tmp_path / "statistics-provenance.json").write_text(
            json.dumps(
                {
                    "source": str(source),
                    "n_points": 1030,
                    "method": "Pearson",
                    "alternative": "two-sided",
                    "multiple_comparison_correction": "none",
                    "excluded_rows": 0,
                    "statistics_execution": "Python/SciPy; native backend only renders the derived matrix",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    source = tmp_path / "concrete_matrix.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Variable", *spec.labels])
        writer.writerows(
            [label, *row] for label, row in zip(spec.labels, spec.correlation_matrix, strict=True)
        )
    preview(
        source,
        tmp_path / engine,
        engine_name=engine,
        template_id="heatmap",
        mapping={"assignments": {"Variable": "category", **{s: "series" for s in spec.labels}}},
        correlation_heatmap_spec=spec.to_dict(),
        engine_home=ROOT / "runtime",
    )
    session = render_confirmed(
        tmp_path / engine / "workflow-preview.json",
        confirmed=True,
        claim="UCI Concrete correlation: fixed original order and unadjusted supplied/derived p-values.",
    )
    assert session["status"] == "verified"
    native = session["current_readback"]
    assert all(verify_readback(spec, native).values())
    assert verify_layout(plan_layout(spec, engine), native)
    assert native["point_count"] == 81
    for row, column, expected in [
        (0, 8, 0.4978319193241571),
        (3, 4, -0.65753290762845),
        (4, 8, 0.36607882718852036),
        (7, 8, 0.32887300077998355),
    ]:
        assert native["correlation_matrix"][row][column] == pytest.approx(expected, abs=1e-13)
    suffixes = ["opju", "png", "pdf", "tif"] if engine == "origin" else ["grf", "png", "pdf"]
    artifact = Path(session["artifacts"]["editable"])
    assert all(artifact.with_suffix("." + suffix).stat().st_size > 0 for suffix in suffixes)
    assert {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources} == hashes
    (tmp_path / "source-integrity.json").write_text(
        json.dumps({"before": hashes, "after": hashes}, indent=2), encoding="utf-8"
    )
