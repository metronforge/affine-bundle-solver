#!/usr/bin/env bash
set -euo pipefail

gate=$1
cc=$2
root=$3
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
common=(-O2 -ffp-contract=off -I"$root/include" -I"$root/src")

cat >"$work/empty-relevant-objdump" <<'EOF'
#!/usr/bin/env bash
if [[ $1 == -t ]]; then
  echo '0000000000000000 g F .text 0000000000000001 bs_verify_unique'
fi
EOF
chmod +x "$work/empty-relevant-objdump"

cat >"$work/empty-full-objdump" <<'EOF'
#!/usr/bin/env bash
if [[ $1 == -t ]]; then
  echo '0000000000000000 g F .text 0000000000000001 bs_verify_unique'
elif [[ " $* " == *' --disassemble='* ]]; then
  printf '0000000000000000 <bs_verify_unique>:\n   0:\tnop\n'
fi
EOF
chmod +x "$work/empty-full-objdump"

cat >"$work/fused-objdump" <<'EOF'
#!/usr/bin/env bash
if [[ $1 == -t ]]; then
  echo '0000000000000000 g F .text 0000000000000001 bs_verify_unique'
elif [[ " $* " == *' --disassemble='* ]]; then
  printf '0000000000000000 <bs_verify_unique>:\n   0:\tnop\n'
else
  printf '0000000000000000 <bs_verify_unique>:\n   0:\t%s\n' "$FAKE_FUSED"
fi
EOF
chmod +x "$work/fused-objdump"

expect_failure() {
  local name=$1
  local expected=$2
  shift 2
  if "$@" >"$work/$name.out" 2>&1; then
    echo "$name: expected failure, got success" >&2
    cat "$work/$name.out" >&2
    return 1
  fi
  if ! grep -Fq "$expected" "$work/$name.out"; then
    echo "$name: expected diagnostic not found: $expected" >&2
    cat "$work/$name.out" >&2
    return 1
  fi
}

expect_failure missing-objdump "not found; cannot inspect objects" \
  env OBJDUMP="$work/missing-objdump" \
  "$gate" "$cc" -- "${common[@]}" -- "$root/src/status_certificate.c"
expect_failure zero-inspected-instructions "no relevant instructions inspected" \
  env OBJDUMP="$work/empty-relevant-objdump" \
  "$gate" "$cc" -- "${common[@]}" -- "$root/src/status_certificate.c"
expect_failure empty-disassembly "no instructions disassembled" \
  env OBJDUMP="$work/empty-full-objdump" \
  "$gate" "$cc" -- "${common[@]}" -- "$root/src/status_certificate.c"
expect_failure unsupported-architecture "no FMA target known" \
  env ABS_FP_CHECK_MACHINE=unsupported-test \
  "$gate" "$cc" -- "${common[@]}" -- "$root/src/status_certificate.c"
expect_failure aarch64-vector-fused-operation \
  "strict kernels contain fused multiply-adds" \
  env ABS_FP_CHECK_MACHINE=aarch64 OBJDUMP="$work/fused-objdump" FAKE_FUSED=fmla \
  "$gate" /bin/true -- "${common[@]}" -- "$root/src/status_certificate.c"
expect_failure x86-alternating-fused-operation \
  "strict kernels contain fused multiply-adds" \
  env ABS_FP_CHECK_MACHINE=x86_64 OBJDUMP="$work/fused-objdump" \
      FAKE_FUSED=vfmaddsub132pd \
  "$gate" /bin/true -- "${common[@]}" -- "$root/src/status_certificate.c"

cat >"$work/status_certificate.c" <<'EOF'
double unrelated(double x) { return x + 1.0; }
EOF
expect_failure missing-target-symbol "target symbol 'bs_verify_unique' absent" \
  "$gate" "$cc" -- -O2 -ffp-contract=off -- "$work/status_certificate.c"

cat >"$work/status_certificate.c" <<'EOF'
double bs_verify_unique(double a, double b, double c) { return a * b + c; }
EOF
expect_failure fused-operation "strict kernels contain fused multiply-adds" \
  "$gate" "$cc" -- -O2 -ffp-contract=fast -- "$work/status_certificate.c"
"$gate" "$cc" -- -O2 -ffp-contract=off -- "$work/status_certificate.c" \
  >"$work/pass.out" 2>&1
grep -q 'fp-contraction check: PASSED' "$work/pass.out"
