# Role-isolation preflight (non-eligible M-only)

Before calibration, single M workers verified direct controls:

- C1 solver: affinity `1,3,6,8`; system OpenBLAS 4; libgomp 1; no
  SciPy/MKL/libiomp mapping; policy pass.
- C1 legacy: affinity `1,3,6,8`; SciPy OpenBLAS 4; system OpenBLAS, MKL,
  libiomp5, and libgomp 1; policy pass.
- C2 solver/legacy: affinity `1`; every mapped runtime 1; policy pass.
- C3 mixed: affinity `1,3,6,8`; system OpenBLAS, SciPy OpenBLAS, MKL,
  libgomp, and libiomp5 all mapped at 4; policy pass for the diagnostic.

These functional preflights were not eligible observations and used accepted
main only. They did not expose candidate timing.

