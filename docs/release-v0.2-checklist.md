# FigureLoom v0.2.0 release verification

Status: **RELEASE-READY — all final automatic gates PASS**. Release preparation starts from accepted Phase 17
`c919407a8238a289ab72175fdecf4b64264eb835` and Phase 16
`8b6e98eca629ed6339db10596ee4bf85ea75ac79`. Renderer/layout/lifecycle behavior is
unchanged by this release; only product version, regenerated runtime manifest,
version test and current release documentation change.

## Original release gates

| Gate | Current release result |
| --- | --- |
| Project/package/installed metadata/CLI version | 0.2.0; version test PASS |
| Full non-GUI regression | 1067 passed, 7 skipped, 42 deselected in 104.76s; exit 0 |
| Origin full isolated native suite | 17/17 PASS, zero skipped; summed execution 974.87s |
| Grapher full isolated native suite | 25/25 PASS, zero skipped; elapsed 1014.97s |
| Concrete A/B/C × both engines | 6/6 PASS, included in the full native counts |
| Fresh p-value OPJU/PNG/PDF/TIF / GRF/PNG/PDF/CSV | All nonempty, reopen/readback/verify PASS |
| Source integrity | Three external CSV SHA-256 values unchanged |
| Lifecycle | Zero newly remaining processes after bounded observations; no process killed |
| Ruff / runtime manifest / diff checks | CI public lint PASS; 441 runtime records; diff checks PASS |
| Public source audit | PASS, 766 files, zero errors; strict staged/worktree and asset checks retained |
| Manual layout / Whole Page GUI | Accepted Phase 17 evidence retained |
| Release commit / annotated local tag | Authorized after all gates; local `v0.2.0`, message `FigureLoom v0.2.0`; no push |

No additional GUI cycle is required because renderer, layout and viewport code
are unchanged. Origin Whole Page mode has no reliable programmatic readback;
retained acceptance is the Phase 17 final GUI check, not a new fake readback.

After removing the machine-specific default raw path, both raw integrations were
rerun with explicit `FIGURELOOM_CONCRETE_RAW`: **2/2 additional PASS**, 28.94s
Origin and 41.28s Grapher. The default-path change affects test source selection,
not calculation or rendering. The main native counts above include the shared
dual-backend test once under Origin (the marker used by the repository), not as
an extra Grapher-suite node. Each exact-node subprocess selects one test; no
suite-wide deselection count applies to these isolated runs.

Fresh Concrete r/p matrices and annotation strings match exactly between
backends. P-value projects' scientific, mapping, legend and physical layout
readback match the GUI-accepted Phase 17 artifacts. Origin remains 11.77×10.92 in,
11 pt annotations and 90° X labels. Whole Page is still applied by the unchanged
native save path; its mode is not invented as a programmatic readback field.

Logs: `.release-v0.2-origin/`, `.release-v0.2-grapher/`,
`.release-v0.2-grapher.log`, `.release-v0.2-final-native-17.log` through `19.log`.
The normalized science/artifact/source comparison is
`.release-v0.2-native-evidence.json`. Evidence is locally excluded from Git;
only documentation, source metadata, audit/provenance fixes and tests are staged.
Existing Origin cleanup HRESULT diagnostics in passing logs remain documented.

## Preparation diagnostics

The first editable metadata installation with `--no-build-isolation` failed
because the test environment lacked `setuptools.build_meta`. The first version
test also failed on stale 0.1.0 source metadata. Repeating installation with the
project's declared isolated build requirements succeeded (no render dependencies
changed), and project/package/installed CLI version test then passed at 0.2.0.
These were preparation failures, not native regression passes.

The initial strict public source audit failed on pre-existing Phase 10–17
inventory gaps, missing fixture provenance, unclassified XLSX binary data,
machine-specific paths and raw CRLF/index differences. The user explicitly
expanded scope to resolve these before committing/tagging. Fifty reviewed
exact paths were added to the allowlist; global path/secret/size rules were not
relaxed. XLSX is classified as binary and inventoried. The asset inventory now
contains 252 CSV/PNG/XLSX records; the two Concrete matrices carry I-Cheng Yeh,
DOI 10.24432/C5PK67 and CC-BY-4.0 attribution as generated real-data statistics,
not synthetic measurements. The original raw table is not bundled.

Raw acceptance source selection is portable via `FIGURELOOM_CONCRETE_RAW`;
the local fallback is `concrete_raw.csv`. A fake executable fixture and the
type-library probe no longer embed absolute machine paths. Raw scientific
files were not modified. Text CRLF was normalized for strict index-byte audit;
historical evidence content remains intact. Existing CI lint found one Phase 17
long line in core and one new audit line; formatting fixes preserve core AST.

The initial Quickstart preview check failed because Pandas default parsing did
not preserve the supplied matrix's exact float values. The example now uses
`float_precision="round_trip"`; all A/B/C API previews execute successfully.
No native success is inferred from this preview-only check.

The first final shared-node invocation had **one pytest setup error** because
its output parent directory had not been created. No COM execution occurred.
The directory was created; the shared-node rerun passed. The first error log is
retained as `.release-v0.2-final-native-17-setup-error.log`, not counted as a pass.

First full non-GUI release run: **1 failed, 1066 passed, 7 skipped, 42 deselected
in 104.11s**. The existing complete-asset test still enumerated only the original
235 assets, omitting the 17 newly inventoried CSV/XLSX fixtures. Its enumeration
now includes those fixture roots and XLSX, and asserts that exactly two Concrete
records retain real-data DOI/license attribution. The corrected targeted test
passed; the subsequent full rerun passed as recorded in the final gate above.

## Boundaries

Legacy Grapher Origin-route coverage remains 7/41. Correlation Heatmap is a
separate production submode/family, with Origin 256-level native Matrix Heatmap
and Grapher 21-class native Class Scatter. Raw Pearson is explicit SciPy
preparation followed by the existing native workflow. Full limitations are in
[release notes](release-v0.2.md); historical v0.1 and Phase 16/17 evidence remains
unchanged.

The existing untracked `.pontius-e2e-test/` is preserved and excluded from the
release commit. No Phase 18, new route, new EditPlan, installer, push, GitHub
Release or package publication was authorized by the original finalization.
The user subsequently authorized the FigureLoom rename and public Git push.

## FigureLoom identity revision before public push (2026-09-28)

The user authorized updating the frozen 0.2.0 identity and its local annotated
release tag before the first successful public push. The canonical public repo
is `yuxian-cell/figureloom`; package, engine module, Skill directory, launcher,
configuration variables and current documentation use FigureLoom / figureloom.
No legacy CLI/config alias is introduced. Historical Git attribution is retained.

Fresh rebrand gates:

- Full non-GUI regression: **1067 passed, 7 skipped, 42 deselected**, 101.90s.
- Origin isolated native coverage: **17/17 PASS**, zero skipped. The final
  shared-plan dual-backend node passed in 53.82s and is counted under Origin.
- Grapher isolated native coverage: **25/25 PASS**, zero skipped, including the
  fresh LSV retry and the final XAS / render-resume-native-edit cases.
- CI control-surface lint: PASS. Runtime manifest: 441 records. Asset inventory:
  252 assets. Strict public source audit: 766 files, zero errors.
- All 161 runtime/Skill Python ASTs match the previous frozen source after the
  exact product-name substitutions. No tracked CSV/XLSX fixture changed.
- Distribution and installed CLI report `figureloom` / FigureLoom 0.2.0.
- No Origin or Grapher process remained after final native checks; no process
  was killed. The initial public push failed atomically because the local clone
  was shallow. Fetching the upstream history restored all reachable objects;
  neither main nor the release tag had reached the public remote at that point.

Rebrand preparation diagnostics are retained separately from successful gates:
first non-GUI run found stale PNG Software metadata and renamed test inventory;
both were corrected. A run concurrent with real Origin jobs failed one mock
smoke assertion because queue progress was emitted. The isolated full rerun above
passed. The first Grapher LSV invocation rendered successfully but its subsequent
verify failed on native COM application shutdown (`0x800706b5`, unknown interface).
The fresh-process retry passed; the initial failure log/report was not discarded.

Evidence is locally excluded from Git under `.release-v0.2-rebrand-*`; original
native suite diagnostics and the untracked `.pontius-e2e-test/` remain preserved.
No scientific route, layout, fit calculation or application lifecycle change was
introduced to suppress these diagnostics. GitHub Release/package publication,
version bump and Phase 18 remain outside this authorization.
