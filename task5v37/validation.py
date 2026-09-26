"""Bounded semantic and stability validation for reconstructed controls."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from task5v31.campaign import atomic_write, canonical_json
from task5v36.analysis import _meaningful_view


BASE_ENV = {
    "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1",
    "OMP_DYNAMIC": "FALSE", "MKL_DYNAMIC": "FALSE", "PYTHONHASHSEED": "0",
}


def run_worker(*, role, bundle, library, openblas_threads, timeout=30):
    environment = os.environ.copy()
    environment.update(BASE_ENV)
    environment["OPENBLAS_NUM_THREADS"] = str(openblas_threads)
    command = ["taskset", "-c", "1,3,6,8", sys.executable, "-m",
               "task5v36.worker", "--role", role, "--configuration", "C1",
               "--bundle", str(Path(bundle).resolve()),
               "--library", str(Path(library).resolve())]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=timeout)
    if completed.returncode:
        return {"ok": False, "returncode": completed.returncode,
                "signal": -completed.returncode if completed.returncode < 0 else None,
                "stdout": completed.stdout, "stderr": completed.stderr,
                "command": command}
    record = json.loads(completed.stdout)
    return {"ok": True, "returncode": 0, "command": command,
            "meaningful": _meaningful_view(record["combined"]),
            "record": record}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--legacy-original", type=Path, required=True)
    parser.add_argument("--legacy-reconstructed", type=Path, required=True)
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--safe-slots", nargs="+", required=True)
    parser.add_argument("--target-slot", default="V31-026")
    parser.add_argument("--stability-runs", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    safe = []
    for slot in args.safe_slots:
        bundle = args.bundle_root / slot
        old = run_worker(role="legacy", bundle=bundle, library=args.legacy_original,
                         openblas_threads=1)
        new = run_worker(role="legacy", bundle=bundle, library=args.legacy_reconstructed,
                         openblas_threads=4)
        safe.append({"slot_id": slot, "original": old, "reconstructed": new,
                     "meaningful_equal": old.get("meaningful") == new.get("meaningful")
                     if old.get("ok") and new.get("ok") else False})

    target_bundle = args.bundle_root / args.target_slot
    target = {
        "L": run_worker(role="legacy", bundle=target_bundle,
                        library=args.legacy_reconstructed, openblas_threads=4),
        "M": run_worker(role="solver", bundle=target_bundle,
                        library=args.main, openblas_threads=4),
        "A": run_worker(role="solver", bundle=target_bundle,
                        library=args.candidate, openblas_threads=4),
    }
    target_equal = (all(value.get("ok") for value in target.values()) and
                    target["L"]["meaningful"] == target["M"]["meaningful"] ==
                    target["A"]["meaningful"])
    stability = [run_worker(role="legacy", bundle=target_bundle,
                            library=args.legacy_reconstructed, openblas_threads=4)
                 for _ in range(args.stability_runs)]
    result = {
        "safe_cases": safe, "target": target,
        "target_meaningful_equal": target_equal,
        "stability": stability,
        "checks": {
            "safe_original_reconstructed_equal": all(row["meaningful_equal"] for row in safe),
            "target_L_M_A_equal": target_equal,
            "ten_target_processes_complete": len(stability) >= 10 and
                all(row.get("ok") for row in stability),
            "stability_router_once": all(
                row.get("record", {}).get("combined", {}).get("router_executions") == 1
                for row in stability),
        },
    }
    atomic_write(args.output, canonical_json(result))
    print(json.dumps({"output": str(args.output), "checks": result["checks"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
