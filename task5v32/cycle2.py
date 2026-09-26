"""Cycle 2: native hotspot attribution with safe profiler fallbacks."""

import argparse
import os
import statistics
import subprocess
import sys
from pathlib import Path

from .diagnostics import BOUNDED_SLOT_IDS, build_trace_library, controlled_environment, rank_native_hotspots, run_slot, write_json


def capture(command, environment=None):
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
    return {"command": command, "return_code": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True); parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args(); tracer = build_trace_library(args.build_dir); environment = controlled_environment(4)
    probe = [sys.executable, "-m", "task5v32.native_trial", "--slot", "V31-027"]
    perf_failure = capture(["perf", "stat", "-e", "task-clock,cycles,instructions", *probe], environment)
    strace_memory = capture(["strace", "-c", "-f", "-e", "trace=brk,mmap,mremap,munmap,madvise,clone,clone3", *probe], environment)
    tool_versions = {"perf": capture(["perf", "--version"]), "strace": capture(["strace", "--version"]),
                     "compiler": capture(["cc", "--version"])}
    raw, summaries = [], []
    for slot_id in BOUNDED_SLOT_IDS:
        raw.append({"slot_id": slot_id, "kind": "warmup", **run_slot(slot_id, preload=tracer)})
        trials = []
        for index in range(args.trials):
            row = run_slot(slot_id, preload=tracer); row.update({"slot_id": slot_id, "kind": "profile", "trial": index})
            raw.append(row); trials.append(row)
        total = statistics.median(row["record"]["timing_ns"]["total_wall"] for row in trials)
        summaries.append({"slot_id": slot_id, "instrumented_total_median_ns": total,
                          "hotspots": rank_native_hotspots([row["trace"] for row in trials], total),
                          "phase_call_counts": {name: statistics.median(row["trace"][name] for row in trials)
                            for name in ("router_count", "unique_gen_count", "infinite_gen_count", "inconsistent_gen_count", "verify_count")}})
    payload = {"cycle": 2, "hypothesis": "a small native function/kernel set explains the dominant phase",
               "preferred_profiler": {"result": "unavailable_due_perf_event_paranoid", **perf_failure},
               "fallback": "LD_PRELOAD monotonic function/kernel interposition plus strace memory syscalls",
               "tool_versions": tool_versions, "strace_memory_probe": strace_memory,
               "raw_records": raw, "summary": summaries,
               "copy_allocation_mapping": [
                 "least_squares_x allocates Ac/B/jpvt/work and copies row-major A to column-major Ac twice per DGELSY",
                 "select_rows_qrcp allocates AT/jpvt/tau/work and forms normalized transposed A twice per QRCP",
                 "smallest_right_vector allocates Ac/s/VT/work and copies A twice per DGESVD",
                 "V31-027 compatible-tall fallback repeatedly invokes left_null_vector_qrcp while scanning null directions"],
               "self_time_limit": "kernel wrappers provide inclusive time; exact instruction-level self time unavailable without perf permission"}
    write_json(args.out, payload)


if __name__ == "__main__":
    main()
