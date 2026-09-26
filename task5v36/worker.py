"""One role-isolated process and exactly one supported combined-API call."""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import resource
import time
from pathlib import Path

from task5v36.ffi import CertifiedLibrary, result_dict
from task5v36.runtime import (CONFIGURATIONS, apply_runtime_policy,
                             capture_telemetry, fingerprint_eligible,
                             validate_telemetry)


def _array(path):
    values = array.array("d")
    with Path(path).open("rb") as stream:
        values.fromfile(stream, Path(path).stat().st_size // values.itemsize)
    if values.itemsize != 8:
        raise RuntimeError("unexpected C double size")
    return values


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _thermal(before, after):
    left = before["throttle"]["signals"]
    right = after["throttle"]["signals"]
    changed = {path: [left.get(path), value] for path, value in right.items()
               if left.get(path) is not None and value > left[path]}
    return {
        "before_frequencies_khz": before["frequencies_khz"],
        "after_frequencies_khz": after["frequencies_khz"],
        "before_temperatures_millic": before["temperatures_millic"],
        "after_temperatures_millic": after["temperatures_millic"],
        "throttle_changes": changed,
        "eligibility": "INVALID_THROTTLE" if changed else
            ("ELIGIBLE_NO_THROTTLE_SIGNAL" if not right else "ELIGIBLE_NO_THROTTLE"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=("solver", "legacy", "mixed"), required=True)
    parser.add_argument("--configuration", choices=tuple(CONFIGURATIONS), required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    args = parser.parse_args()

    metadata = json.loads((args.bundle / "metadata.json").read_text())
    m, n = metadata["slot"]["m"], metadata["slot"]["n"]
    library = CertifiedLibrary(args.library)
    if args.role in ("legacy", "mixed"):
        import numpy as np
        from scipy.linalg import lstsq
        a = np.fromfile(args.bundle / "a.f64le", dtype="<f8").reshape(m, n)
        b = np.fromfile(args.bundle / "b.f64le", dtype="<f8")
    else:
        a = _array(args.bundle / "a.f64le")
        b = _array(args.bundle / "b.f64le")

    config = CONFIGURATIONS[args.configuration]
    policy = config.roles["legacy" if args.role in ("legacy", "mixed") else "solver"]
    settings = apply_runtime_policy(policy)
    before = validate_telemetry(capture_telemetry(settings))
    fingerprint = fingerprint_eligible(before, policy)

    xt = None
    preliminary_ns = 0
    wall_start, cpu_start = time.perf_counter_ns(), time.process_time_ns()
    if args.role == "legacy":
        started = time.perf_counter_ns()
        xt, *_ = lstsq(a, b, lapack_driver="gelsd")
        preliminary_ns = time.perf_counter_ns() - started
    api_started = time.perf_counter_ns()
    rc, raw = library.call_raw(a, b, xt, m, n)
    api_ns = time.perf_counter_ns() - api_started
    total_wall = time.perf_counter_ns() - wall_start
    cpu_ns = time.process_time_ns() - cpu_start
    combined = result_dict(rc, raw)
    after = validate_telemetry(capture_telemetry(settings))

    output = {
        "slot_id": metadata["slot"]["slot_id"], "role": args.role,
        "configuration": args.configuration,
        "input": {"matrix_sha256": metadata["matrix_sha256"],
                  "rhs_sha256": metadata["rhs_sha256"], "m": m, "n": n},
        "expected": {"standard_oracle": metadata["standard_oracle"],
                     "contract_oracle": metadata["contract_oracle"]},
        "library": {"path": str(args.library.resolve()),
                    "sha256": _sha256(args.library)},
        "combined": combined,
        "timing_ns": {"legacy_preliminary_lstsq": preliminary_ns,
                      "combined_c_api": api_ns, "total_wall": total_wall},
        "cpu_time_ns": cpu_ns,
        "peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "runtime": after, "runtime_before_timing": before,
        "runtime_policy": fingerprint,
        "thermal": _thermal(before, after),
        "active_compute_budget": config.active_threads,
    }
    print(json.dumps(output, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
