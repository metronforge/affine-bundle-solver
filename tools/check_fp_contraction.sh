#!/usr/bin/env bash
# Structural check of the strict kernels' floating-point contract: no fused
# multiply-add may be emitted from strict-kernel sources.
#
# Usage:
#   tools/check_fp_contraction.sh CC [CC-ARGS...] -- FLAGS... -- SOURCES...
#
# The caller passes the exact compiler command and the exact flags it uses for
# the strict kernels (build.sh and CMake each pass their own), so the check
# covers the flags that are actually in force rather than a restated copy.
#
# Why this is needed.  -frounding-math makes GCC and clang honour the dynamic
# rounding mode, but it does not forbid floating-point contraction.  GCC's
# default in GNU C mode is -ffp-contract=fast and clang's is =on, so on any
# FMA-capable target (x86-64-v3, -march=native, every aarch64) a*b+c may be
# fused into one instruction with a single rounding.  In the directed-rounding
# code of this repository every such site computes an upward-rounded sum of
# non-negative terms, so a fused result is still a valid upper bound; the
# certificates stay sound.  What breaks is reproducibility: eta_S^+ then
# depends on the build target, and a kernel rewritten without `volatile`
# guards would silently change bits.  The strict kernels are therefore
# compiled with -ffp-contract=off, and this script proves that the flag set in
# force actually suppresses fusion.
#
# The portable x86-64 baseline has no FMA, so compiling for it would pass
# vacuously.  The sources are therefore compiled here for an FMA-capable
# target: -march=x86-64-v3 on x86_64; the default target on aarch64, where FMA
# is always available.  On any other architecture the check fails closed
# rather than pretending to have checked.
set -euo pipefail

cc=(); flags=(); sources=(); part=0
for a in "$@"; do
  if [[ $a == "--" ]]; then part=$((part + 1)); continue; fi
  case $part in
    0) cc+=("$a") ;;
    1) flags+=("$a") ;;
    *) sources+=("$a") ;;
  esac
done
if ((${#cc[@]} == 0 || ${#sources[@]} == 0 || part != 2)); then
  echo "usage: $0 CC [ARGS...] -- FLAGS... -- SOURCES..." >&2
  exit 2
fi

OBJDUMP=${OBJDUMP:-objdump}
if ! command -v "$OBJDUMP" >/dev/null 2>&1; then
  echo "fp-contraction check: FAILED -- '$OBJDUMP' not found; cannot inspect objects" >&2
  exit 1
fi

machine=${ABS_FP_CHECK_MACHINE:-$(uname -m)}
case $machine in
  x86_64)
    target=(-march=x86-64-v3)
    fused='\bvfn?m(add|sub)[0-9]*(p|s)[sd]\b' ;;
  aarch64|arm64)
    target=()
    fused='\bfn?m(add|sub)\b' ;;
  *)
    echo "fp-contraction check: FAILED -- no FMA target known for '$machine'" >&2
    exit 1 ;;
esac

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
total_fused=0
for src in "${sources[@]}"; do
  obj="$work/$(basename "${src%.c}").o"
  case $(basename "$src") in
    formation_guard.c) expected_symbol=fg_sketch_formation_eps ;;
    status_certificate.c) expected_symbol=bs_verify_unique ;;
    certified_api.c) expected_symbol=bsolve_certified_diag_api ;;
    *)
      echo "fp-contraction check: FAILED -- no expected target symbol registered for $src" >&2
      exit 1 ;;
  esac
  "${cc[@]}" "${flags[@]}" "${target[@]}" -c "$src" -o "$obj"
  if ! symbols=$("$OBJDUMP" -t "$obj"); then
    echo "fp-contraction check: FAILED -- could not inspect symbols in $src" >&2
    exit 1
  fi
  if ! grep -Eq "[[:space:]]${expected_symbol}$" <<<"$symbols"; then
    echo "fp-contraction check: FAILED -- target symbol '$expected_symbol' absent from $src" >&2
    exit 1
  fi
  if ! relevant=$("$OBJDUMP" -d --no-show-raw-insn --disassemble="$expected_symbol" "$obj"); then
    echo "fp-contraction check: FAILED -- could not disassemble target symbol '$expected_symbol' in $src" >&2
    exit 1
  fi
  nrelevant=$(grep -c -E '^[[:space:]]+[0-9a-f]+:' <<<"$relevant" || true)
  if ((nrelevant == 0)); then
    echo "fp-contraction check: FAILED -- no relevant instructions inspected for '$expected_symbol' in $src" >&2
    exit 1
  fi
  if ! listing=$("$OBJDUMP" -d --no-show-raw-insn "$obj"); then
    echo "fp-contraction check: FAILED -- could not disassemble $src" >&2
    exit 1
  fi
  # A listing without instructions would make the check vacuous.
  ninsn=$(grep -c -E '^[[:space:]]+[0-9a-f]+:' <<<"$listing" || true)
  if ((ninsn == 0)); then
    echo "fp-contraction check: FAILED -- no instructions disassembled from $src" >&2
    exit 1
  fi
  nfused=$(grep -c -E "$fused" <<<"$listing" || true)
  echo "fp-contraction check: $src: $nfused fused multiply-add(s) in $ninsn instructions; target '$expected_symbol' has $nrelevant instructions (${target[*]:-default target})"
  if ((nfused > 0)); then
    grep -E "$fused" <<<"$listing" | head -5 | sed 's/^/    /'
  fi
  total_fused=$((total_fused + nfused))
done

if ((total_fused > 0)); then
  echo "fp-contraction check: FAILED -- strict kernels contain fused multiply-adds." >&2
  echo "The strict-kernel flags must include -ffp-contract=off." >&2
  exit 1
fi
echo "fp-contraction check: PASSED (${#sources[@]} sources)"
