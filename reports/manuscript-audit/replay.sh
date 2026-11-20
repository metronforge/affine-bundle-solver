#!/usr/bin/env bash
# From any directory in the audit checkout. Dependencies are those of build.sh,
# build_paper.sh and the project property suites, plus system BLAS/LAPACK for the rank probes.
set -euo pipefail
root=$(git rev-parse --show-toplevel)
base=1df77461faf407320dab200d025fa846b2151502
tip=$(git -C "$root" rev-parse HEAD)
ev="$root/reports/manuscript-audit/evidence"
temp=$(mktemp -d)
trap 'rm -rf -- "$temp"' EXIT
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ABS_CERT_UNIQUE_THREADS=1

# The stock property command writes into results/. Use disposable checkouts.
for name in base final; do
    revision=$base
    if [[ $name == final ]]; then revision=$tip; fi
    tree="$temp/$name"
    git clone --quiet --no-hardlinks --no-checkout "$root" "$tree"
    git -C "$tree" checkout --quiet --detach "$revision"
    (
        cd "$tree"
        bash build.sh
        bash build_paper.sh > "$temp/$name.tex.log"
        pdfinfo paper.pdf | grep -E '^Pages:'
        if grep -Ei 'undefined references|Citation .* undefined|Reference .* undefined|Overfull .[hv]box' paper.log; then exit 1; fi
        if grep -Ei 'Warning--|error message' paper.blg; then exit 1; fi
    )
done
export ABS_LIB_DIR="$temp/base"
cc -std=c11 -I"$root/include" "$ev/cert-probe.c" -L"$ABS_LIB_DIR" \
    -Wl,-rpath,"$ABS_LIB_DIR" -lcertified_solver -lstatus_verifier -o "$temp/cert-probe"
"$temp/cert-probe"
cc -std=gnu11 -O2 -fopenmp -frounding-math -fno-fast-math -ffp-contract=off \
    -I"$root/include" -I"$root/src" "$ev/cert-norm.c" -lm -o "$temp/cert-norm"
"$temp/cert-norm"
cd "$root"
bash reports/manuscript-audit/evidence/rank-replay.sh
python3 "$ev/cert-fixtures.py"
python3 "$ev/empirical-exact.py" "$temp/base"
python3 "$ev/empirical-rerun.py" "$temp/base"
python3 "$ev/empirical-records.py"
cd "$temp/final"
export ABS_LIB_DIR="$PWD"
python3 tests/check_paper_claims.py --audit-performance-artifacts . --require-publication-ready
python3 tests/check_paper_claims.py
