# Correlation fixtures

`demo_correlation.csv` is the explicitly synthetic Phase 16 matrix.
Its signed AR(1) matrix is positive definite. P-values are supplied synthetic
test inputs for threshold formatting; they are not experimental results.

`concrete_correlation.csv` and `concrete_pvalues.csv` are the user-supplied
9-variable matrices from the UCI Concrete Compressive Strength data (1030
observations), used with permission as Phase 17 acceptance fixtures. Original
variable names/order are preserved. Diagonal p=0 is an input convention;
diagonal stars are always omitted. No multiple comparison correction is applied.

The 1030-row raw user file is not bundled. The optional native `raw` acceptance
case uses `EDITAPLOT_CONCRETE_RAW` (local baseline `E:/prism/concrete_raw.csv`)
and SciPy's Pearson, two-sided test. It skips if that source or SciPy is absent.
SciPy is a test/data-analysis dependency only; no production correlation
algorithm or renderer dependency was added. Source hashes are recorded before
and after the native render. Four anchored correlations are tested separately
from the visual layout.
