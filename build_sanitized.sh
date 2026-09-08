#!/usr/bin/env bash
# build_sanitized.sh -- build the libraries under AddressSanitizer and
# UndefinedBehaviorSanitizer.
#
# This is a DIAGNOSTIC configuration, not the shipping one.  Two deliberate
# differences from build.sh:
#
#   1. -O1 instead of -O3/-O2.  Sanitizers need frame pointers and unoptimised
#      bounds to report useful locations.
#
#   2. The fast router is built WITHOUT -ffast-math.  That flag implies
#      -ffinite-math-only, under which the router's use of NaN and infinity as
#      sentinel values is formally undefined behaviour; UBSan would report
#      every one of those sites and drown the memory findings we are actually
#      looking for.  Running the same source without the flag still exercises
#      the identical control flow, allocation pattern and pointer arithmetic,
#      which is what ASan and the non-float UBSan checks examine.
#
# What this configuration is therefore able to find: out-of-bounds access,
# use-after-free, leaks, integer overflow, misaligned or null pointer use,
# invalid shifts.  What it deliberately does not examine: the floating-point
# semantics of the shipping -ffast-math build, which are covered instead by
# the rounding and MXCSR probes in build.sh and by the certificate batteries.

set -euo pipefail
cd "$(dirname "$0")"

CC=${CC:-gcc}
SAN=${SAN:-address,undefined}

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

SANFLAGS="-fsanitize=${SAN} -fno-omit-frame-pointer -fno-sanitize-recover=undefined"
COMMON="-std=c17 -O1 -g -Wall -Wextra ${SANFLAGS}"

echo "sanitizers: ${SAN}"
echo "openblas  : $(basename "$OPENBLAS")"

# --- strict proof kernels: same floating-point contract as the shipping build
# Public headers live in include/, and the sources select their BLAS symbol
# names through src/blas_symbols.h.  This script links SciPy's bundled
# OpenBLAS, whose Fortran symbols carry a scipy_ prefix, so it asks for that
# naming explicitly -- exactly as build.sh does.
INCLUDES="-Iinclude -Isrc"
BLAS_DEFS="-DABS_SCIPY_BLAS"

$CC $INCLUDES $BLAS_DEFS $COMMON -frounding-math -fno-fast-math -fPIC -c src/formation_guard.c \
  -o formation_guard.san.o

$CC $INCLUDES $BLAS_DEFS $COMMON -frounding-math -fno-fast-math -shared -fPIC \
  src/status_certificate.c -o libstatus_verifier.so -lm

# --- fast router: same source, sanitizable floating-point mode (see header).
# Built before the audit API because the latter links against it.
$CC $INCLUDES $BLAS_DEFS $COMMON -fopenmp -fPIC -c src/bsolver.c -o bsolver.san.o

$CC $SANFLAGS -shared -fopenmp bsolver.san.o formation_guard.san.o \
  -o libaffine_bundle_solver.so "$OPENBLAS" -Wl,-rpath,"$RPATH" \
  -latomic -lm

# --- audit API: links against both of the above, mirroring build.sh
$CC $INCLUDES $BLAS_DEFS $COMMON -frounding-math -fno-fast-math -shared -fPIC \
  src/certified_api.c -o libcertified_solver.so \
  -L. -laffine_bundle_solver -lstatus_verifier \
  "$OPENBLAS" -Wl,-rpath,'$ORIGIN' -Wl,-rpath,"$RPATH" -lm

rm -f formation_guard.san.o bsolver.san.o

echo "Built sanitized libraries (diagnostic configuration; do not ship)."
