"""Run the pre-registered Task-5 v3.4 Cycle-1 attribution once."""

from __future__ import annotations

import csv
import io
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

from task5v31.campaign import generate_manifest
from task5v32.diagnostics import write_binary_input

from .diagnostics import (
    CAMPAIGN_ID,
    FROZEN_SPEEDUPS,
    parse_trace_line,
    select_shared_target,
    triangular_product_terms,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "campaign-v3.4"
SOLVER = Path("/projects/research-assistant/task5-solver-v34")
BUILD = SOLVER / "build-v34-baseline"
LIB = BUILD / "libcertified_solver.so"
TRACE = OUT / "native_trace.so"
SLOTS = ("V31-025", "V31-026", "V31-027")
FROZEN_CANDIDATE_TOTAL_NS = {
    "V31-025": 83_644_000,
    "V31-026": 164_322_000,
    "V31-027": 112_474_000,
}


def environment(preload: bool = False) -> dict[str, str]:
    env = os.environ.copy()
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                 "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[name] = "4"
    env["TASK5_SOLVER_LIB"] = str(LIB)
    env["LD_LIBRARY_PATH"] = str(BUILD)
    if preload:
        env["TASK5_V32_TRACE"] = "1"
        env["LD_PRELOAD"] = str(TRACE)
    return env


def invoke(command: list[str], *, preload: bool = False) -> dict[str, object]:
    completed = subprocess.run(command, cwd=ROOT, env=environment(preload), text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return {"command": command, "stdout": completed.stdout, "stderr": completed.stderr}


def prepare_tools_and_inputs() -> list[list[str]]:
    (OUT / "inputs").mkdir(parents=True, exist_ok=True)
    commands = [
        ["cc", "-shared", "-fPIC", "-O2", "-I", str(SOLVER / "include"),
         str(ROOT / "task5v34/native_trace.c"), "-o", str(TRACE), "-ldl", "-pthread"],
        ["cc", "-O2", "-frounding-math", "-fno-fast-math",
         str(ROOT / "task5v34/fenv_cost.c"), "-o", str(OUT / "fenv_cost"), "-lm"],
        ["cc", "-std=c11", "-O2", "-frounding-math", "-fno-fast-math",
         "-I", str(SOLVER / "include"), str(ROOT / "task5v34/unique_verifier_probe.c"),
         "-L", str(BUILD), "-lcertified_solver", "-laffine_bundle_solver",
         "-lstatus_verifier", "-lm", f"-Wl,-rpath,{BUILD}",
         "-o", str(OUT / "unique_verifier_probe")],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    slots = {slot["slot_id"]: slot for slot in generate_manifest()["slots"]}
    for slot_id in SLOTS:
        write_binary_input(OUT / "inputs" / f"{slot_id}.bin", slots[slot_id])
    return commands


def median(rows: list[dict[str, object]], key: str) -> float:
    return statistics.median(float(row[key]) for row in rows)


def parse_probe(text: str) -> dict[str, object]:
    lines = text.splitlines()
    meta = dict(field.split("=", 1) for field in lines[0].split(",")[1:])
    if int(meta["gen_rc"]):
        return {"meta": meta, "verifier_trials": [], "kernel_trials": []}
    kernel_index = next(i for i, line in enumerate(lines) if line.startswith("kernel_meta,"))
    verifier = list(csv.DictReader(io.StringIO("\n".join(lines[1:kernel_index]))))
    kernel_meta = dict(field.split("=", 1) for field in lines[kernel_index].split(",")[1:])
    kernel = list(csv.DictReader(io.StringIO("\n".join(lines[kernel_index + 1:]))))
    def numeric(rows: list[dict[str, str]]) -> list[dict[str, object]]:
        return [{key: float(value) if key == "eta" else int(value) for key, value in row.items()}
                for row in rows]
    return {"meta": {key: int(value) for key, value in meta.items()},
            "verifier_trials": numeric(verifier),
            "kernel_meta": {"mismatches": int(kernel_meta["mismatches"]),
                            "max_abs": float(kernel_meta["max_abs"])},
            "kernel_trials": numeric(kernel)}


def main() -> None:
    build_commands = prepare_tools_and_inputs()
    raw: dict[str, object] = {"campaign_id": CAMPAIGN_ID, "protocol": {
        "warmups_per_slot": 1, "production_trials_per_slot": 5,
        "instrumented_trials_per_slot": 5, "direct_probe_trials": 5,
        "selective_reruns": False, "threads": 4}, "build_commands": build_commands}
    phase_runs: dict[str, object] = {}
    trace_runs: dict[str, object] = {}
    probes: dict[str, object] = {}
    for slot in SLOTS:
        command = [sys.executable, "-m", "task5v31.runner", "--slot", slot]
        warmup = invoke(command)
        rows = [json.loads(invoke(command)["stdout"]) for _ in range(5)]
        phase_runs[slot] = {"warmup": json.loads(warmup["stdout"]), "trials": rows}

        trace_command = [sys.executable, "-m", "task5v32.native_trial", "--slot", slot]
        trace_warmup = invoke(trace_command, preload=True)
        traced = [invoke(trace_command, preload=True) for _ in range(5)]
        trace_runs[slot] = {
            "warmup": {"record": json.loads(trace_warmup["stdout"]),
                       "trace": parse_trace_line(trace_warmup["stderr"])},
            "trials": [{"record": json.loads(item["stdout"]),
                        "trace": parse_trace_line(item["stderr"])} for item in traced],
        }

        probe_command = [str(OUT / "unique_verifier_probe"),
                         str(OUT / "inputs" / f"{slot}.bin"), "5"]
        probe = invoke(probe_command)
        probes[slot] = {"command": probe_command, "raw_stdout": probe["stdout"],
                       "parsed": parse_probe(probe["stdout"])}

    fenv_command = [str(OUT / "fenv_cost"), "1000000", "11"]
    fenv = invoke(fenv_command)
    fenv_rows = [{key: float(value) if key == "net_per_call_ns" else int(value)
                  for key, value in row.items()}
                 for row in csv.DictReader(io.StringIO(fenv["stdout"]))]
    raw.update({"phase_runs": phase_runs, "trace_runs": trace_runs, "direct_probes": probes,
                "fenv_cost": {"command": fenv_command, "raw_stdout": fenv["stdout"],
                              "trials": fenv_rows}})

    phases = []
    target_evidence = []
    ranked = []
    for slot in SLOTS:
        rows = phase_runs[slot]["trials"]
        production = median([row["timing_ns"] for row in rows], "combined_c_api")
        caller = median([row["timing_ns"] for row in rows], "materialization")
        validation_values = []
        harness_values = []
        for row in rows:
            timing = row["timing_ns"]
            validation_values.append(sum(timing[name] for name in (
                "standard_svd", "standard_qr", "standard_lstsq", "contract_oracle", "validation")))
            accounted = sum(timing[name] for name in (
                "materialization", "standard_svd", "standard_qr", "standard_lstsq",
                "contract_oracle", "combined_c_api", "validation", "serialization"))
            harness_values.append(timing["serialization"] + max(0, timing["total_wall"] - accounted))
        total = median([row["timing_ns"] for row in rows], "total_wall")
        phases.append({"slot_id": slot, "production_api_median_ns": production,
                       "required_caller_preparation_median_ns": caller,
                       "correctness_validation_median_ns": statistics.median(validation_values),
                       "harness_only_median_ns": statistics.median(harness_values),
                       "total_wall_median_ns": total})
        traces = [row["trace"] for row in trace_runs[slot]["trials"]]
        for component in ("router", "unique_gen", "infinite_gen", "inconsistent_gen",
                          "unique_verify", "infinite_verify", "inconsistent_verify",
                          "dgelsy", "dgeqp3", "dgesvd", "dormqr"):
            ranked.append({"slot_id": slot, "component": component,
                           "inclusive_median_ns": median(traces, f"{component}_ns"),
                           "invocation_count_median": median(traces, f"{component}_count")})
        parsed = probes[slot]["parsed"]
        kernel_rows = parsed["kernel_trials"]
        if kernel_rows:
            old = median(kernel_rows, "baseline_kernel_ns")
            new = median(kernel_rows, "direct_kernel_ns")
            verify = median(parsed["verifier_trials"], "verify_ns")
            saved = max(0.0, old - new)
            fraction = min(saved, verify) / FROZEN_CANDIDATE_TOTAL_NS[slot]
            supported = parsed["kernel_meta"]["max_abs"] == 0.0 and saved > 0.0
            target_evidence.append({"slot_id": slot, "production_fraction": fraction,
                                    "supported": supported, "baseline_kernel_median_ns": old,
                                    "direct_kernel_median_ns": new,
                                    "unique_verifier_median_ns": verify,
                                    "frozen_candidate_total_ns": FROZEN_CANDIDATE_TOTAL_NS[slot],
                                    "structural_counts": triangular_product_terms(int(parsed["meta"]["n"]))})
        else:
            target_evidence.append({"slot_id": slot, "production_fraction": 0.0,
                                    "supported": False, "reason": "unique witness not applicable"})
    decision = select_shared_target("unique_verifier_triangular_zero_and_copy_work",
                                    target_evidence, FROZEN_SPEEDUPS)
    summary = {"campaign_id": CAMPAIGN_ID, "phase_separation": phases,
               "ranked_native_components": sorted(ranked, key=lambda row: row["inclusive_median_ns"], reverse=True),
               "selected_target_evidence": target_evidence, "decision": decision,
               "same_mode_fesetround_net_median_ns": statistics.median(
                   row["net_per_call_ns"] for row in fenv_rows),
               "measurement_note": "instrumented traces and direct probes are excluded from production timing"}
    (OUT / "evidence").mkdir(parents=True, exist_ok=True)
    (OUT / "timings").mkdir(parents=True, exist_ok=True)
    (OUT / "evidence" / "cycle-01-raw.json").write_text(
        json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
    (OUT / "evidence" / "cycle-01-summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps(summary["decision"], sort_keys=True))


if __name__ == "__main__":
    main()
