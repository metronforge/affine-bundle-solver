#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
archive=$1
work=$2
source_snapshot=$3
source_api=$4
test ! -e "$work"
mkdir -p "$work"
unset ABS_LIB_DIR LD_LIBRARY_PATH LD_PRELOAD DYLD_LIBRARY_PATH DYLD_FALLBACK_LIBRARY_PATH DYLD_INSERT_LIBRARIES
unset CMAKE_PREFIX_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH LIBRARY_PATH
prefix=$(python "$root/tools/package_binary_sdk.py" extract "$archive" "$work/extracted")
cp -R "$root/tests/consumer" "$work/consumer-source"
cp "$root/tests/binary_sdk_smoke.c" "$work/consumer-source/sdk-smoke.c"
cd "$work"
cmake -S consumer-source -B consumer-build \
  "-Daffine-bundle-solver_DIR=$prefix/lib/cmake/affine-bundle-solver" \
  -DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF -DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build consumer-build --verbose
for exe in consumer consumer_certified_diag consumer_certified_diag_cpp; do
  python "$root/tools/check_sdk_consumer.py" "$prefix" "$work/consumer-build/$exe"
done
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig"
export PKG_CONFIG_LIBDIR="$PKG_CONFIG_PATH"
pkg-config --cflags --libs affine-bundle-solver
for fixture in main certified_diag sdk-smoke; do
  # pkg-config's shell words are the public consumption contract.
  ${CC:-cc} "consumer-source/$fixture.c" $(pkg-config --cflags --libs affine-bundle-solver) \
    -lm -Wl,-rpath,"$prefix/lib" -o "pkg-$fixture"
  python "$root/tools/check_sdk_consumer.py" "$prefix" "$work/pkg-$fixture" > "$fixture.json"
done
python - "$source_api" sdk-smoke.json <<'PY'
import json, sys
assert json.load(open(sys.argv[1])) == json.load(open(sys.argv[2])), 'packaged policy/stream semantic disagreement'
PY
python "$root/tests/compare_builds.py" --snapshot "$prefix/lib" --output binary-semantic.json
python "$root/tests/compare_builds.py" --compare-snapshots "$source_snapshot" binary-semantic.json
target=$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["platform"])' "$prefix/BUILD-INFO.json")
python "$root/tools/inspect_binary_sdk.py" "$prefix" "$target" --forbid "$root" --output inspection.json
python "$root/tools/check_missing_sdk_dependency.py" "$prefix" inspection.json missing-dependencies.json
echo 'Archive C/C++/diagnostic/pkg-config/policy/stream/certificate consumers: PASS'
