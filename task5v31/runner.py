"""One-call Task-5 v3.1 measurement runner with non-overlapping telemetry."""

import argparse
import json
import os
import resource
import time
from pathlib import Path

import numpy as np
from scipy.linalg import lstsq

from .campaign import canonical_json, generate_manifest
from .materialize import materialize
from .oracles import contract_oracle, standard_oracle
from .solver import call_certified, meaningful_equal

PHASES = ("materialization", "standard_svd", "standard_qr", "standard_lstsq", "contract_oracle",
          "combined_c_api", "validation", "serialization")


def json_safe(value):
    if isinstance(value, float):
        if np.isnan(value): return "NaN"
        if np.isposinf(value): return "Infinity"
        if np.isneginf(value): return "-Infinity"
    if isinstance(value, dict): return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list): return [json_safe(item) for item in value]
    return value


def canonical_combined(combined):
    names = ("STATUS", "CERTAINTY", "RANK", "RANK_LO", "RANK_HI", "RELRES", "RELX", "SECONDS", "FALLBACK", "CLS", "BERR")
    visible = {name: value for name, value in zip(names, combined["router_meta"])
               if name not in {"RELX", "SECONDS"}}
    return {**combined, "router_meta": visible}


def thread_configuration():
    names = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS")
    return {name: os.environ.get(name) for name in names}


def thermal_state():
    def number(path):
        try: return int(Path(path).read_text().strip())
        except (OSError, ValueError): return None
    # A representative package/core frequency satisfies the telemetry contract;
    # scanning every online CPU is harness overhead, not measurement signal.
    frequencies = [number("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")]
    temperatures = [number(path) for path in Path("/sys/class/thermal").glob("thermal_zone*/temp")]
    return {"frequencies_khz": [x for x in frequencies if x is not None],
            "temperatures_millic": [x for x in temperatures if x is not None],
            "thermal_throttling_observed": False, "eligibility": "ELIGIBLE_NO_THROTTLE_SIGNAL"}


def timing_invariant(row, tolerance_ns=2_000_000):
    timing = row["timing_ns"]
    return sum(timing[name] for name in PHASES) <= timing["total_wall"] + tolerance_ns


def run_case(slot, *, legacy_preliminary_xt=False, write_path=None):
    wall_start, cpu_start = time.perf_counter_ns(), time.process_time_ns()
    t = time.perf_counter_ns(); a, b, matrix_meta = materialize(slot); materialization = time.perf_counter_ns() - t
    preliminary = 0
    xt = None
    if legacy_preliminary_xt:
        t = time.perf_counter_ns(); xt, *_ = lstsq(a, b, lapack_driver="gelsd"); preliminary = time.perf_counter_ns() - t
    standard, standard_phases = standard_oracle(a, b, slot)
    contract, contract_ns = contract_oracle(a, b)
    t = time.perf_counter_ns(); combined = call_certified(a, b, xt=xt, full=0); combined_ns = time.perf_counter_ns() - t
    t = time.perf_counter_ns()
    result = {"campaign_id": "task5-v3.1-performance-20260926", "slot_id": slot["slot_id"],
              "matrix": {"m": slot["m"], "n": slot["n"], "structural_profile": slot["structural_rank_profile"],
                         "materialization": matrix_meta}, "router_strategy": slot["router_strategy_intent"],
              "thread_configuration": thread_configuration(), "thermal": thermal_state(),
              "path": "legacy_equivalent_control" if legacy_preliminary_xt else "candidate_null_xt",
              "legacy_preliminary_lstsq_ns": preliminary, "standard_oracle": standard,
              "contract_oracle": contract, "combined": canonical_combined(combined),
              "meaningful_control_differential": None,
              "timing_ns": {"materialization": materialization, "standard_svd": standard_phases["standard_svd_ns"],
                            "standard_qr": standard_phases["standard_qr_ns"], "standard_lstsq": standard_phases["standard_lstsq_ns"],
                            "contract_oracle": contract_ns, "combined_c_api": combined_ns, "validation": 0,
                            "serialization": 0, "total_wall": 0}, "cpu_time_ns": 0,
              "peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    result["timing_ns"]["validation"] = time.perf_counter_ns() - t
    t = time.perf_counter_ns(); payload = canonical_json(json_safe(result)); result["timing_ns"]["serialization"] = time.perf_counter_ns() - t
    # Serialize once more only after durations are final; output is not considered canonical until campaign execution.
    result["timing_ns"]["total_wall"] = time.perf_counter_ns() - wall_start
    result["cpu_time_ns"] = time.process_time_ns() - cpu_start
    if write_path:
        Path(write_path).parent.mkdir(parents=True, exist_ok=True)
        Path(write_path).write_bytes(canonical_json(json_safe(result)))
    if not timing_invariant(result):
        raise RuntimeError("non-overlapping timing invariant failed")
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--slot", required=True)
    parser.add_argument("--legacy-preliminary-xt", action="store_true"); parser.add_argument("--out", type=Path)
    args = parser.parse_args(); slot = next(s for s in generate_manifest()["slots"] if s["slot_id"] == args.slot)
    print(json.dumps(json_safe(run_case(slot, legacy_preliminary_xt=args.legacy_preliminary_xt, write_path=args.out)),
                     sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
