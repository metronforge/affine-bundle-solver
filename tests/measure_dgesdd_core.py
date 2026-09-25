#!/usr/bin/env python3
"""Bounded direct-core A/B, with raw samples and proven LAPACK symbol paths.

Usage: python3 tests/measure_dgesdd_core.py BASE_SRC BASE_BUILD CAND_SRC CAND_BUILD OUT.json
Both build trees must contain the project's strictly compiled formation-guard object.
"""
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
CASES = ((64, 128), (128, 128), (128, 64), (128, 512))


def compile_one(source, build, objdir, label, symbol):
    guard = build / "CMakeFiles/abs_formation_guard_obj.dir/src/formation_guard.c.o"
    if not guard.is_file(): raise RuntimeError(f"missing strict guard object: {guard}")
    object_file = objdir / f"{label}.o"
    binary = objdir / label
    compile_command = ["cc", "-O3", "-fopenmp", "-ffast-math", "-I" + str(source / "src"),
                       "-I" + str(source / "include"), "-c",
                       str(ROOT / "tests/test_dgesdd_core_state.c"), "-o", str(object_file)]
    subprocess.run(compile_command, check=True)
    symbols = subprocess.check_output(["nm", "-u", str(object_file)], text=True)
    if symbol not in symbols or ("dgesdd_" if symbol == "dgesvd_" else "dgesvd_") in symbols:
        raise RuntimeError(f"{label}: expected only {symbol} in undefined symbols")
    link_command = ["cc", "-fopenmp", str(object_file), str(guard),
                    "-lopenblas", "-latomic", "-lm", "-o", str(binary)]
    subprocess.run(link_command, check=True)
    return binary, compile_command, link_command


def run(binary, rows, n, env):
    result = subprocess.run([str(binary), "--measure", str(rows), str(n)],
                            check=True, text=True, capture_output=True, env=env)
    return json.loads(result.stdout)


def main(args):
    base_source, base_build, cand_source, cand_build, output = map(Path, args)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
               MKL_NUM_THREADS="1", BLIS_NUM_THREADS="1")
    with tempfile.TemporaryDirectory(prefix="dgesdd-core-ab-") as directory:
        place = Path(directory)
        a, ac, al = compile_one(base_source, base_build, place, "baseline", "dgesvd_")
        b, bc, bl = compile_one(cand_source, cand_build, place, "candidate", "dgesdd_")
        result = {"method": "direct core_svd_state, same harness/compiler flags; strict build guard object",
                  "threads": {key: env[key] for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "BLIS_NUM_THREADS")},
                  "warmups": 1, "repetitions": 5, "order": "AB, BA, AB, BA, AB",
                  "baseline_symbol": "dgesvd_", "candidate_symbol": "dgesdd_",
                  "compile_commands": [ac, bc], "link_commands": [al, bl], "cases": []}
        for rows, n in CASES:
            run(a, rows, n, env); run(b, rows, n, env)
            samples = {"baseline": [], "candidate": []}
            for repetition in range(5):
                for key, binary in (("baseline", a), ("candidate", b)) if repetition % 2 == 0 else (("candidate", b), ("baseline", a)):
                    samples[key].append(run(binary, rows, n, env))
            basetimes = [x["seconds"] for x in samples["baseline"]]
            candtimes = [x["seconds"] for x in samples["candidate"]]
            med_a = statistics.median(basetimes)
            med_b = statistics.median(candtimes)
            result["cases"].append({"rows": rows, "n": n, "raw": samples,
                                    "baseline_median_s": med_a,
                                    "baseline_mad_s": statistics.median(abs(x-med_a) for x in basetimes),
                                    "candidate_median_s": med_b,
                                    "candidate_mad_s": statistics.median(abs(x-med_b) for x in candtimes),
                                    "ratio": med_b / med_a,
                                    "vt_baseline_bytes": 8 * n * n,
                                    "vt_candidate_bytes": 8 * min(rows, n) * n})
    output.write_text(json.dumps(result, indent=2) + "\n")
    for item in result["cases"]:
        print(f"{item['rows']}x{item['n']}: {item['ratio']:.3f}x, VT {item['vt_baseline_bytes']} -> {item['vt_candidate_bytes']} B")
    print(f"raw samples: {output}")


if __name__ == "__main__":
    if len(sys.argv) != 6: raise SystemExit(__doc__)
    main(sys.argv[1:])
