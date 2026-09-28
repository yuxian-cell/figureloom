# Asset and data provenance

This open-source release contains project-created teaching/verification fixtures, original project
assets, and one author-provided support-payment QR image that the author explicitly approved for
public display.

The 2026-07-30 public-release review covered every listed CSV and PNG, including synthetic/generated
status, patient/clinical identifiers, labels, embedded PNG text/EXIF, payment-identifier intent, and
redistribution boundaries.
The manifest also binds the inventory builder and gallery fixture generator by SHA-256; changing
either script requires regenerating and manually reviewing the manifest.

The current gallery manifest retains 50 verified cases across 41 public plotting routes. The public
page displays 48 cases. The two non-displayed heatmap PNGs remain only as regression and audit
history; they are not alternate public showcase entries.

- Teaching and native integration CSV/XLSX fixtures are synthetic. The two
  `tests/fixtures/correlation_heatmap/concrete_*.csv` matrices are an explicit
  exception: derived Pearson/two-sided unadjusted p-value statistics from the
  public UCI Concrete dataset, not synthetic measurements. Attribution: Yeh, I.
  (1998), *Concrete Compressive Strength*, https://doi.org/10.24432/C5PK67,
  CC BY 4.0. The original 1030-row table is not bundled. Changes preserve the
  original variable identities and generate statistical matrices.
- The two GSAS/GSAS-II XRD fixtures are project-authored teaching tables. They contain no patient,
  clinical, instrument-account, or third-party experimental records.
- Gallery PNG files were exported by the verified local editable-figure workflow from those
  synthetic fixtures. The repository does not include the corresponding local logs, plans, OPJU,
  PDF, or TIF evidence.
- The PL/TRPL example uses neutral project-generated sample names and lifetimes; it does not copy
  the material labels or numeric values from the visual reference that motivated the chart family.
- The DSC, NMR, FTIR/IR, XPS comparison, UV–Vis, PL temperature-series, 3D trajectory,
  3D dual-density baseline-locator, and dense
  matrix fixtures are deterministic project-authored teaching data. The public gallery displays
  the real Origin-rendered 30×30 matrix only; the smaller annotated matrix and 40×40 matrix remain
  in the retained verification inventory. None reproduces values, labels, conclusions, arrows,
  logos, or layouts from supplied paper screenshots.
- The palette cards and selectors are original layouts generated from the machine-readable palette
  catalog. Scientific gallery and palette assets do not include reference covers, watermarks, logos,
  screenshots, or journal layouts.
- `assets/support/wechat-tip.png` is an author-provided WeChat Pay support QR image, intentionally
  published as the voluntary support destination shown at the end of both READMEs. It is not
  scientific data, a user upload, or a reusable plotting asset. It contains a masked payee display
  name and payment-interface branding by design, but no EXIF or PNG text metadata and no PHI.
  WeChat/WeChat Pay names and marks remain the property of their respective owner and are shown only
  to identify the payment method.
- The application icon is an original generic chart icon. The fixed XPS preview is generated from a
  synthetic template fixture.
- No distributed asset is presented as a Nature, Science, ACS, OriginLab, WeChat, clinical, or
  journal specification, affiliation, or endorsement.

[`assets/provenance-manifest.json`](assets/provenance-manifest.json) freezes the SHA-256, size,
classification, synthetic/generated status, source attribution, and PNG text metadata
for every tracked CSV, PNG and XLSX. The v0.2 fixture inventory update was authorized
on 2026-09-28; the earlier asset review remains historical evidence. Rebuild
it with `tools/build_asset_provenance.py` and review the diff before each release.
