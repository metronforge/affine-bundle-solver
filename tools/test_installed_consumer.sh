#!/usr/bin/env bash
# Run after CTest. Moving the build and install prefix catches stale paths.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
build=$1
work=$2
mkdir -p "$work"
cmake --install "$build" --prefix "$work/prefix"
mv "$work/prefix" "$work/relocated"
prefix="$work/relocated"
test -f "$prefix/include/affine_bundle/router.h"
test ! -f "$prefix/include/affine_bundle/formation_guard.h"
test ! -f "$prefix/include/affine_bundle/blas_symbols.h"
cp -R "$root/tests/consumer" "$work/source"
mv "$build" "$build.unavailable"
trap 'mv "$build.unavailable" "$build"' EXIT
cd "$work"
unset ABS_LIB_DIR LD_LIBRARY_PATH DYLD_LIBRARY_PATH DYLD_FALLBACK_LIBRARY_PATH
cmake -S source -B consumer-build -DCMAKE_PREFIX_PATH="$prefix"
cmake --build consumer-build
for exe in consumer consumer_certified_diag consumer_certified_diag_cpp; do
  "./consumer-build/$exe"
  if [[ $(uname -s) == Darwin ]]; then
    otool -L "./consumer-build/$exe"
  else
    ldd "./consumer-build/$exe"
  fi
done
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig"
pkg-config --cflags --libs affine-bundle-solver
for src in main certified_diag; do
  # pkg-config intentionally returns a shell word list.
  ${CC:-cc} "source/$src.c" $(pkg-config --cflags --libs affine-bundle-solver) \
    -lm -Wl,-rpath,"$prefix/lib" -o "pkg-$src"
  "./pkg-$src"
done
echo 'installed CMake C/C++ and pkg-config consumers: PASS (relocated prefix, build unavailable)'
