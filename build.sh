#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# A manifest describes the last *successful* invocation, not merely the last
# binary still present on disk. Invalidate it before discovery or compilation
# so every failure path is fail-closed.
rm -f .abs-build-manifest.json
PYTHON=${PYTHON:-python3}
CC=${CC:-gcc}
read -r -a CC_ARGV <<< "$CC"
if ((${#CC_ARGV[@]} == 0)); then
  echo "CC must contain a compiler command" >&2
  exit 2
fi
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

# The sources call BLAS through the names selected in src/blas_symbols.h.
# build.sh is the manuscript reproduction path and links SciPy's bundled
# OpenBLAS, whose Fortran symbols carry a scipy_ prefix, so it asks for that
# naming explicitly.  A CMake build without this define links an ordinary
# system BLAS instead.
BLAS_DEFS="-DABS_SCIPY_BLAS"
INCLUDES="-Iinclude -Isrc"
read -r -a ARCH_ARGV <<< "$ARCH_FLAGS"
read -r -a INCLUDE_ARGV <<< "$INCLUDES"
read -r -a BLAS_DEF_ARGV <<< "$BLAS_DEFS"

# Strict compressed-rank witness: a-posteriori provenance bounds, separate from fast-math.
FORMATION_ARGV=("${CC_ARGV[@]}" -O2 -fPIC "${INCLUDE_ARGV[@]}"
  "${BLAS_DEF_ARGV[@]}" -c src/formation_guard.c -o formation_guard.o
  -frounding-math -fno-fast-math)
"${FORMATION_ARGV[@]}"

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
ROUTER_COMPILE_ARGV=("${CC_ARGV[@]}" -O3 "${ARCH_ARGV[@]}" -fopenmp -fPIC
  -ffast-math "${INCLUDE_ARGV[@]}" "${BLAS_DEF_ARGV[@]}" -c src/bsolver.c
  -o bsolver.o)
ROUTER_LINK_ARGV=("${CC_ARGV[@]}" -shared -fopenmp bsolver.o
  formation_guard.o -o libaffine_bundle_solver.so "$OPENBLAS"
  -Wl,-rpath,"$RPATH" -latomic -lm)
"${ROUTER_COMPILE_ARGV[@]}"
"${ROUTER_LINK_ARGV[@]}"
rm -f formation_guard.o bsolver.o

# The certificate checker has a deliberately separate floating-point contract.
"${CC_ARGV[@]}" -O2 -frounding-math -fno-fast-math src/rounding_probe.c \
  -o .rounding_probe -lm
./.rounding_probe
rm -f .rounding_probe

"${CC_ARGV[@]}" -O2 -shared -fPIC "${INCLUDE_ARGV[@]}" \
  src/status_certificate.c -o libstatus_verifier.so \
  -frounding-math -fno-fast-math -lm

"${CC_ARGV[@]}" -O2 -shared -fPIC "${INCLUDE_ARGV[@]}" \
  "${BLAS_DEF_ARGV[@]}" src/certified_api.c -o libcertified_solver.so \
  -frounding-math -fno-fast-math -L. -laffine_bundle_solver -lstatus_verifier \
  "$OPENBLAS" -Wl,-rpath,'$ORIGIN' -Wl,-rpath,"$RPATH" -lm

# Separate compilation of the fast and strict kernels is necessary but not
# sufficient: FTZ/DAZ are runtime MXCSR state and a -ffast-math link can set
# them process-wide at load time, which would make the subnormal-range
# certificate checks vacuous.  Verify that it does not happen here.
"${CC_ARGV[@]}" -O2 -frounding-math -fno-fast-math src/mxcsr_probe.c \
  -o .mxcsr_probe -ldl
./.mxcsr_probe ./libaffine_bundle_solver.so ./libcertified_solver.so
rm -f .mxcsr_probe

# Publish provenance only after every build and runtime probe succeeds. The
# JSON receives the exact expanded arrays used above, not reconstructed flags.
argv_json() {
  "$PYTHON" -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "$@"
}
CC_JSON=$(argv_json "${CC_ARGV[@]}")
ROUTER_COMPILE_JSON=$(argv_json "${ROUTER_COMPILE_ARGV[@]}")
ROUTER_LINK_JSON=$(argv_json "${ROUTER_LINK_ARGV[@]}")
COMPILER_OUTPUT=$("${CC_ARGV[@]}" --version)
COMPILER_IDENTITY=${COMPILER_OUTPUT%%$'\n'*}
BUILD_SHA=$(git rev-parse HEAD)
BUILD_TREE_SHA=$(git rev-parse 'HEAD^{tree}')
if [[ -n $(git status --porcelain) ]]; then
  BUILD_DIRTY=true
else
  BUILD_DIRTY=false
fi
BUILD_SCRIPT_SHA=$(sha256sum build.sh | awk '{print $1}')
ROUTER_SHA=$(sha256sum libaffine_bundle_solver.so | awk '{print $1}')
OPENBLAS_SHA=$(sha256sum "$OPENBLAS" | awk '{print $1}')
MANIFEST_TMP=$(mktemp .abs-build-manifest.json.tmp.XXXXXX)
trap 'rm -f "$MANIFEST_TMP"' EXIT
"$PYTHON" - "$MANIFEST_TMP" "$BUILD_SHA" "$BUILD_TREE_SHA" \
  "$BUILD_DIRTY" "$BUILD_SCRIPT_SHA" "$CC_JSON" "$COMPILER_IDENTITY" \
  "$ROUTER_COMPILE_JSON" "$ROUTER_LINK_JSON" "$ARCH_FLAGS" \
  "$ROUTER_SHA" "$OPENBLAS" "$OPENBLAS_SHA" <<'PY'
import datetime
import json
import os
import pathlib
import sys

(target, git_sha, tree_sha, dirty, script_sha, compiler_json,
 compiler_identity, compile_json, link_json, arch_flags, router_sha,
 openblas_path, openblas_sha) = sys.argv[1:]
router_path = pathlib.Path("libaffine_bundle_solver.so").resolve()
openblas_path = pathlib.Path(openblas_path).resolve()
manifest = {
    "schema_version": 1,
    "built_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z"),
    "source": {"git_sha": git_sha, "git_tree_sha": tree_sha,
               "git_dirty": dirty == "true"},
    "build_script": {"path": "build.sh", "sha256": script_sha},
    "compiler": {"command_argv": json.loads(compiler_json),
                 "identity": compiler_identity},
    "router": {
        "compile_argv": json.loads(compile_json),
        "link_argv": json.loads(link_json),
        "arch_flags": arch_flags,
        "library": {"basename": router_path.name,
                    "resolved_path": str(router_path), "sha256": router_sha},
    },
    "openblas": {"basename": openblas_path.name,
                 "resolved_path": str(openblas_path),
                 "sha256": openblas_sha},
}
pathlib.Path(target).write_text(json.dumps(manifest, indent=2) + "\n")
json.loads(pathlib.Path(target).read_text())
os.replace(target, ".abs-build-manifest.json")
PY
trap - EXIT

echo "Built fast solver, strict verifier, and certified audit API."
