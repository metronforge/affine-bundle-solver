#!/usr/bin/env bash
# build_coverage.sh -- build with gcov instrumentation to report which branches
# the test suite actually exercises.
#
# Why this exists.  The property batteries run over ten thousand checks, which
# is easy to mistake for thorough path coverage.  It is not the same thing:
# measured on the reference platform the batteries take roughly 37% of the
# branches in the router and 40% in the formation guard at least once.  The
# uncovered remainder is concentrated in the escalation and fallback routes --
# solve_blockprefix_qr, secant_refresh, try_tall_qr_unique_core, the
# source-QRCP paths -- which are precisely the routes that only fire when the
# fast path declines.  Random well-conditioned inputs rarely reach them.
#
# This is reported and not enforced.  A coverage threshold in CI reliably
# produces tests written to move the number rather than to check anything,
# which would undermine the batteries rather than strengthen them.  The number
# is here to be looked at when deciding what to test next.
#
# The build is -O0 for the router so that line and branch attribution is
# meaningful; this is a measurement configuration, not a shipping one.

set -euo pipefail
cd "$(dirname "$0")"

CC=${CC:-gcc}

OPENBLAS=$(python3 - <<'PY'
import glob, os, scipy
base = os.path.dirname(scipy.__file__)
cands = sorted(glob.glob(os.path.join(base, '..', 'scipy.libs',
                                      'libscipy_openblas*.so')))
if not cands:
    raise SystemExit('no scipy OpenBLAS found; pip install scipy')
print(os.path.realpath(cands[0]))
PY
)
RPATH=$(dirname "$OPENBLAS")

rm -f ./*.gcda ./*.gcno ./*.gcov

# Public headers live in include/, and the sources select their BLAS symbol
# names through src/blas_symbols.h.  This script links SciPy's bundled
# OpenBLAS, whose Fortran symbols carry a scipy_ prefix, so it asks for that
# naming explicitly -- exactly as build.sh does.
INCLUDES="-Iinclude -Isrc"
BLAS_DEFS="-DABS_SCIPY_BLAS"

$CC $INCLUDES $BLAS_DEFS -O0 -g --coverage -fopenmp -fPIC -c src/bsolver.c -o bsolver.cov.o
$CC $INCLUDES $BLAS_DEFS -O2 --coverage -frounding-math -fno-fast-math -fPIC \
  -c src/formation_guard.c -o formation_guard.cov.o

$CC --coverage -shared -fopenmp bsolver.cov.o formation_guard.cov.o \
  -o libaffine_bundle_solver.so "$OPENBLAS" -Wl,-rpath,"$RPATH" -latomic -lm

$CC $INCLUDES $BLAS_DEFS -O2 --coverage -frounding-math -fno-fast-math -shared -fPIC \
  src/status_certificate.c -o libstatus_verifier.so -lm

$CC $INCLUDES $BLAS_DEFS -O2 --coverage -frounding-math -fno-fast-math -shared -fPIC \
  src/certified_api.c -o libcertified_solver.so \
  -L. -laffine_bundle_solver -lstatus_verifier \
  "$OPENBLAS" -Wl,-rpath,'$ORIGIN' -Wl,-rpath,"$RPATH" -lm

echo "Built instrumented libraries (measurement configuration; do not ship)."
