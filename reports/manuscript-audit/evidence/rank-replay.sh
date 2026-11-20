#!/usr/bin/env bash
# Run from the repository root on Linux with the audited libraries built.
set -euo pipefail
: "${ABS_LIB_DIR:=$PWD}"
export ABS_LIB_DIR OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
tmp=$(mktemp -d)
trap 'rm -r "$tmp"' EXIT
src=reports/manuscript-audit/evidence
strict=(-O2 -frounding-math -fno-fast-math -ffp-contract=off)
system_linalg=(-l:liblapack.so.3 -l:libblas.so.3 -lm)
gcc --version | head -n1
sha256sum "$ABS_LIB_DIR/libaffine_bundle_solver.so" "$ABS_LIB_DIR/libcertified_solver.so"
gcc -O2 -Iinclude "$src/rank-public.c" -L"$ABS_LIB_DIR" -Wl,-rpath,"$ABS_LIB_DIR" -lcertified_solver -laffine_bundle_solver -lm -o "$tmp/public"
"$tmp/public"
gcc -O3 -march=native -fopenmp -ffast-math -Iinclude -Isrc -ffunction-sections -c "$src/rank-local.c" -o "$tmp/local.o"
gcc "${strict[@]}" -Isrc -c src/formation_guard.c -o "$tmp/fg.o"
gcc -Wl,--gc-sections -Wl,--wrap=fg_core_normalized_eps -fopenmp "$tmp/local.o" "$tmp/fg.o" "${system_linalg[@]}" -o "$tmp/local"
"$tmp/local" > "$tmp/local.txt"
cat "$tmp/local.txt"
python3 - "$tmp/local.txt" <<'PY'
from fractions import Fraction
from pathlib import Path
import sys
line = Path(sys.argv[1]).read_text().splitlines()[-1]
prefix, entries = line.split(" stored=")
fields = dict(token.split("=") for token in prefix.split()[2:])
def number(s):
    return Fraction(float.fromhex(s))
target = number(fields["raw"]) / number(fields["divisor"])
error_sq = sum((number(x) - target)**2 for x in entries.split())
eps = number(fields["eps"])
print("Exact rational trace budget violated:", error_sq > eps**2,
      "norm/error-budget ratio", float(error_sq / eps**2)**0.5)
PY
gcc -std=c11 -Isrc "${strict[@]}" "$src/rank-frob.c" "${system_linalg[@]}" -o "$tmp/frob"
"$tmp/frob"
for test in test_threshold_contract.py test_core_rank_boundary.py test_blockprefix_guard.py; do
    python3 "tests/$test" > "$tmp/$test.log"
    tail -1 "$tmp/$test.log"
done
