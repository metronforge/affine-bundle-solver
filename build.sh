#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}
CC=${CC:-gcc}
# Architecture flags for the fast router.  Default is -march=native for
# best local performance; override with ARCH_FLAGS="" (or a specific -march)
# for a portable binary.  -march=native fixes the instruction set to the build
# machine and enables FMA contraction, so wall times and last-bit results of
# the fast router are build-machine dependent.  The strict proof kernels below
# never use these flags.
#
# The expansion uses "-" and not ":-" deliberately: an explicitly empty
# ARCH_FLAGS must stay empty, whereas ":-" would treat it as unset and
# silently restore -march=native, making a "portable" build identical to a
# native one.
ARCH_FLAGS=${ARCH_FLAGS--march=native}
OPENBLAS="$($PYTHON - <<'PY'
import glob, os, scipy
base=os.path.dirname(scipy.__file__)
xs=glob.glob(os.path.join(base,'..','scipy.libs','libscipy_openblas*.so'))
if not xs: raise SystemExit('SciPy OpenBLAS shared library not found')
print(os.path.realpath(xs[0]))
PY
)"
RPATH=$(dirname "$OPENBLAS")

# Strict compressed-rank witness: a-posteriori provenance bounds, separate from fast-math.
$CC -O2 -fPIC -c src/formation_guard.c -o formation_guard.o \
  -frounding-math -fno-fast-math

# Fast numerical route.  Sketch/proposal arithmetic may use fast-math, but no
# source-rank lower bound is trusted until formation_guard.o verifies it.
# -latomic is required under clang.  For reduction(max:) on a double, clang
# emits the generic __atomic_compare_exchange / __atomic_load libcalls from
# libatomic, whereas GCC routes the same construct through libgomp
# (GOMP_atomic_start/end).  Without it the clang build links but the shared
# object fails to load with an undefined symbol.  Under GCC the flag is
# harmless: --as-needed drops the unused dependency.
#
# Compilation and linking are deliberately SEPARATE steps, and -ffast-math is
# passed only to the compile step.  When -ffast-math appears on the link line,
# the driver may add a startup object (crtfastmath.o and equivalents) whose
# constructor sets the MXCSR FTZ and DAZ bits for the WHOLE PROCESS at load
# time.  Those bits are runtime state, so they would then also apply to the
# strict proof kernels running in the same process, flushing to zero exactly
# the subnormal inputs the certificate battery is built to exercise -- those
# checks would pass vacuously.
#
# This is compiler-dependent and was observed, not assumed: GCC 13 does not
# add the constructor, clang 18 does.  The mxcsr probe below verifies the
# resulting library at run time and fails the build if the mode leaks, so a
# toolchain that behaves differently again cannot slip through silently.
$CC -O3 $ARCH_FLAGS -fopenmp -fPIC -ffast-math -c src/bsolver.c \
  -o bsolver.o
$CC -shared -fopenmp bsolver.o formation_guard.o \
  -o libaffine_bundle_solver.so "$OPENBLAS" -Wl,-rpath,"$RPATH" \
  -latomic -lm
rm -f formation_guard.o bsolver.o

# The certificate checker has a deliberately separate floating-point contract.
$CC -O2 -frounding-math -fno-fast-math src/rounding_probe.c \
  -o .rounding_probe -lm
./.rounding_probe
rm -f .rounding_probe

$CC -O2 -shared -fPIC src/status_certificate.c -o libstatus_verifier.so \
  -frounding-math -fno-fast-math -lm

$CC -O2 -shared -fPIC src/certified_api.c -o libcertified_solver.so \
  -frounding-math -fno-fast-math -L. -laffine_bundle_solver -lstatus_verifier \
  "$OPENBLAS" -Wl,-rpath,'$ORIGIN' -Wl,-rpath,"$RPATH" -lm

# Separate compilation of the fast and strict kernels is necessary but not
# sufficient: FTZ/DAZ are runtime MXCSR state and a -ffast-math link can set
# them process-wide at load time, which would make the subnormal-range
# certificate checks vacuous.  Verify that it does not happen here.
$CC -O2 -frounding-math -fno-fast-math src/mxcsr_probe.c -o .mxcsr_probe -ldl
./.mxcsr_probe ./libaffine_bundle_solver.so ./libcertified_solver.so
rm -f .mxcsr_probe

echo "Built fast solver, strict verifier, and certified audit API."