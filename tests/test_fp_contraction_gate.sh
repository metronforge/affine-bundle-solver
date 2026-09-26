#!/usr/bin/env bash
set -euo pipefail

gate=$1
cc=$2
root=$3
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
common=(-O2 -ffp-contract=off -I"$root/include" -I"$root/src")

expect_failure() {
  local name=$1
  shift
  if "$@" >"$work/$name.out" 2>&1; then
    echo "$name: expected failure, got success" >&2
    cat "$work/$name.out" >&2
    return 1
  fi
}

expect_failure missing-objdump env OBJDUMP="$work/missing-objdump" \
  "$gate" "$cc" -- "${common[@]}" -- "$root/src/status_certificate.c"

expect_failure empty-disassembly env OBJDUMP=/bin/true \
  "$gate" "$cc" -- "${common[@]}" -- "$root/src/status_certificate.c"

expect_failure unsupported-architecture env ABS_FP_CHECK_MACHINE=unsupported-test \
  "$gate" "$cc" -- "${common[@]}" -- "$root/src/status_certificate.c"

cat >"$work/status_certificate.c" <<'EOF'
double unrelated(double x) { return x + 1.0; }
EOF
expect_failure missing-target-symbol \
  "$gate" "$cc" -- -O2 -ffp-contract=off -- "$work/status_certificate.c"

cat >"$work/status_certificate.c" <<'EOF'
double bs_verify_unique(double a, double b, double c) { return a * b + c; }
EOF
expect_failure fused-operation \
  "$gate" "$cc" -- -O2 -ffp-contract=fast -- "$work/status_certificate.c"

"$gate" "$cc" -- -O2 -ffp-contract=off -- "$work/status_certificate.c" \
  >"$work/pass.out" 2>&1
grep -q 'fp-contraction check: PASSED' "$work/pass.out"
