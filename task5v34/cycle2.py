"""Capture baseline/candidate correctness evidence for the single Cycle-2 change."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from task5v33.performance import semantic_view

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "campaign-v3.4/evidence/cycle-02-implementation.json"
BUILDS = {
    "baseline": Path("/projects/research-assistant/task5-solver-v34/build-v34-baseline"),
    "candidate": Path("/projects/research-assistant/task5-solver-v34/build-v34-candidate"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(slot: str, build: Path) -> dict[str, object]:
    env = os.environ.copy()
    env.update({name: "4" for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                        "MKL_NUM_THREADS", "BLIS_NUM_THREADS",
                                        "NUMEXPR_NUM_THREADS")})
    env["TASK5_SOLVER_LIB"] = str(build / "libcertified_solver.so")
    env["LD_LIBRARY_PATH"] = str(build)
    command = [sys.executable, "-m", "task5v31.runner", "--slot", slot]
    completed = subprocess.run(command, cwd=ROOT, env=env, check=True, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {"command": command, "record": json.loads(completed.stdout),
            "stderr": completed.stderr}


def main() -> None:
    slots = ("V31-025", "V31-026", "V31-027")
    records = {name: {slot: run(slot, build) for slot in slots}
               for name, build in BUILDS.items()}
    comparisons = []
    for slot in slots:
        left = records["baseline"][slot]["record"]
        right = records["candidate"][slot]["record"]
        comparisons.append({
            "slot_id": slot,
            "semantic_equal": semantic_view(left) == semantic_view(right),
            "baseline_router_executions": left["combined"]["router_executions"],
            "candidate_router_executions": right["combined"]["router_executions"],
            "baseline_combined_ns": left["timing_ns"]["combined_c_api"],
            "candidate_combined_ns": right["timing_ns"]["combined_c_api"],
        })
    payload = {
        "campaign_id": "task5-v3.4-shared-overhead-20260926",
        "red": {"observed": True, "failure": "undefined test-only product counter symbols",
                "command": "cmake --build build-v34-red --target abs_unique_verifier_structure_test -j4"},
        "green": {"observed": True, "structural_products_n4": 60,
                  "baseline_products_n4": 128,
                  "command": "ctest --test-dir build-v34-red -R unique_verifier_structure --output-on-failure"},
        "libraries": {name: {"certified_sha256": sha256(build / "libcertified_solver.so"),
                              "verifier_sha256": sha256(build / "libstatus_verifier.so")}
                      for name, build in BUILDS.items()},
        "ownership": {"removed_allocations": ["lrow[n]", "ucol[n]"],
                      "retained_allocations": ["pos[m]", "evec[n]"],
                      "global_mutable_production_state": False,
                      "failure_cleanup": "pos and evec freed; caller rounding mode restored"},
        "comparisons": comparisons,
        "all_meaningful_equal": all(row["semantic_equal"] for row in comparisons),
        "one_router_execution": all(row["candidate_router_executions"] == 1 for row in comparisons),
        "records": records,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"all_meaningful_equal": payload["all_meaningful_equal"],
                      "one_router_execution": payload["one_router_execution"]}, sort_keys=True))


if __name__ == "__main__":
    main()
