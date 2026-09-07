# WELL1033 source record

The release bundles the Harwell--Boeing/Matrix Market surveying least-squares matrix `well1033` and its published right-hand side so the real-matrix control does not depend on network access.

Acquisition endpoints used by `experiments/acquire_well1033.py`:

- matrix: `https://math.nist.gov/pub/MatrixMarket2/Harwell-Boeing/lsq/well1033.mtx.gz`
- RHS: `https://math.nist.gov/pub/MatrixMarket2/Harwell-Boeing/lsq/well1033_rhs1.mtx.gz`

SHA-256 of the decompressed bundled files:

- `well1033.mtx`: `9953cb6091a268afb6725bd92c26cdea68c8897b2d9a31a0656b0c0022e25f0c`
- `well1033_rhs1.mtx`: `2a9e1c688987c63facdd646cdc8441c447ea5d708de38c8ccdec9fcb91007e31`

The experiment intentionally densifies the matrix before passing it to the dense research implementation. It is therefore a numerical-structure and negative-performance control, not a sparse-performance benchmark.
