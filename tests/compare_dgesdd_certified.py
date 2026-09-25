#!/usr/bin/env python3
"""Isolated DGESVD/DGESDD certified differential; one router DSO per process.

Usage: python3 tests/compare_dgesdd_certified.py BASE_BUILD CANDIDATE_BUILD OUT.json
The output contains raw per-case public fields and mapped DSO identities.
"""
import ctypes
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np


FIELDS = [
    ("fast_status", ctypes.c_int), ("fast_certainty", ctypes.c_int),
    ("rank_estimate", ctypes.c_int), ("rank_lo", ctypes.c_int),
    ("rank_hi", ctypes.c_int), ("eta_x", ctypes.c_double),
    ("certified_status", ctypes.c_int), ("eta_status", ctypes.c_double),
    ("generator_code", ctypes.c_int), ("verifier_code", ctypes.c_int),
    ("accepted_status_mask", ctypes.c_int), ("eta_unique", ctypes.c_double),
    ("eta_infinite", ctypes.c_double), ("eta_inconsistent", ctypes.c_double),
    ("unique_generator_code", ctypes.c_int), ("unique_verifier_code", ctypes.c_int),
    ("infinite_generator_code", ctypes.c_int), ("infinite_verifier_code", ctypes.c_int),
    ("inconsistent_generator_code", ctypes.c_int), ("inconsistent_verifier_code", ctypes.c_int),
]
FLOAT_FIELDS = {name for name, kind in FIELDS if kind is ctypes.c_double}
ROUTER_FIELDS = ("status", "certainty", "rank", "rank_lo", "rank_hi",
                 "relres", "relx", "seconds", "fallback", "raw_class", "backward_error")
ROUTER_INTEGERS = {"status", "certainty", "rank", "rank_lo", "rank_hi",
                   "fallback", "raw_class"}
DP = ctypes.POINTER(ctypes.c_double)


class Result(ctypes.Structure):
    _fields_ = FIELDS


def arrays():
    rng = np.random.default_rng(20260925)
    cases = []

    def add(name, a, b, x):
        cases.append((name, np.ascontiguousarray(a), np.ascontiguousarray(b),
                      np.ascontiguousarray(x)))

    for name, shape in (("wide", (32, 64)), ("square", (48, 48)),
                        ("tall", (96, 32))):
        a = rng.standard_normal(shape); x = rng.standard_normal(shape[1])
        add(name, a, a @ x, x)
    a = np.zeros((48, 64)); x = np.zeros(64); add("zero", a, a @ x, x)
    u = rng.standard_normal((96, 12)); v = rng.standard_normal((12, 32))
    a = u @ v; x = rng.standard_normal(32); add("rankdef", a, a @ x, x)
    a = rng.standard_normal((96, 32)); x = rng.standard_normal(32)
    b = a @ x; b[3] += 1.0; add("inconsistent", a, b, x)
    q1, _ = np.linalg.qr(rng.standard_normal((96, 32)))
    q2, _ = np.linalg.qr(rng.standard_normal((32, 32)))
    for gap in (0.0, 1e-14, 1e-11, 1e-6):
        a = q1 @ np.diag(np.r_[np.ones(31), gap]) @ q2.T
        x = np.ones(32); add(f"gap-{gap:g}", a, a @ x, x)
    a = rng.standard_normal((32, 64)); x = rng.standard_normal(64)
    add("scaled-wide", 1e-6 * a, 1e-6 * (a @ x), x)
    a = rng.standard_normal((96, 32)); x = rng.standard_normal(32)
    add("scaled-tall", 1e6 * a, 1e6 * (a @ x), x)
    return cases


def encode(value):
    if isinstance(value, (float, np.floating)) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("+Inf" if value > 0 else "-Inf")
    return value.item() if isinstance(value, np.generic) else value


def worker(build):
    build = build.resolve()
    certified = build / "libcertified_solver.so"
    router = build / "libaffine_bundle_solver.so"
    if not certified.is_file() or not router.is_file():
        raise RuntimeError(f"missing build libraries in {build}")
    lib = ctypes.CDLL(str(certified))
    mapped = {Path(line.rsplit(None, 1)[-1]).resolve() for line in
              Path("/proc/self/maps").read_text().splitlines()
              if "libaffine_bundle_solver.so" in line}
    if mapped != {router}:
        raise RuntimeError(f"wrong or multiple mapped routers: {mapped} != {router}")
    lib.bsolve_certified_api.argtypes = [DP, DP, DP, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_ulonglong, ctypes.c_int,
                                        ctypes.POINTER(Result)]
    lib.bsolve_certified_api.restype = ctypes.c_int
    lib.bsolve_router_meta_api.argtypes = [DP, DP, DP, ctypes.c_int, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                           ctypes.c_ulonglong, ctypes.c_int, DP]
    lib.bsolve_last_core_rank_interval_api.argtypes = [ctypes.POINTER(ctypes.c_int)]
    lib.bsolve_last_core_qr_rank_api.restype = ctypes.c_int
    lib.bsolve_last_grey_total_api.restype = ctypes.c_int
    lib.bsolve_last_orth_eta_api.restype = ctypes.c_double
    records = []
    for name, a, b, x in arrays():
        input_hash = hashlib.sha256(a.tobytes() + b.tobytes() + x.tobytes()).hexdigest()
        for seed in (7, 20260925, 777):
            out = Result()
            rc = lib.bsolve_certified_api(a.ctypes.data_as(DP), b.ctypes.data_as(DP),
                                          x.ctypes.data_as(DP), *a.shape, 1, 2, 2,
                                          seed, 0, ctypes.byref(out))
            meta = (ctypes.c_double * 11)()
            lib.bsolve_router_meta_api(a.ctypes.data_as(DP), b.ctypes.data_as(DP),
                                       x.ctypes.data_as(DP), *a.shape, 1, 2, 2,
                                       seed, 0, meta)
            if (int(meta[0]), int(meta[1]), int(meta[2]), int(meta[3]), int(meta[4])) != (
                out.fast_status, out.fast_certainty, out.rank_estimate, out.rank_lo, out.rank_hi):
                raise RuntimeError(f"{name}: certified/router semantic mismatch")
            interval = (ctypes.c_int * 2)()
            lib.bsolve_last_core_rank_interval_api(interval)
            records.append({"case": name, "shape": a.shape, "seed": seed,
                            "input_sha256": input_hash, "return_code": rc,
                            "router_calls_in_worker": 2,  # one inside certified, one explicit
                            "fields": {key: encode(getattr(out, key)) for key, _ in FIELDS},
                            "router_meta": {key: encode(meta[i]) for i, key in enumerate(ROUTER_FIELDS)
                                            if key != "seconds"},
                            "diagnostics": {
                                "core_rank_interval": list(interval),
                                "core_qr_rank": lib.bsolve_last_core_qr_rank_api(),
                                "grey_total": lib.bsolve_last_grey_total_api(),
                                "orth_eta": encode(lib.bsolve_last_orth_eta_api()),
                            }})
    return {"build": str(build), "certified_sha256": hashlib.sha256(certified.read_bytes()).hexdigest(),
            "router_sha256": hashlib.sha256(router.read_bytes()).hexdigest(),
            "mapped_router": str(router), "records": records}


def same(a, b, tolerance=1e-12):
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    if isinstance(a, float) or isinstance(b, float):
        return math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)
    return a == b


def parent(base, candidate, output):
    children = []
    for build in (base, candidate):
        run = subprocess.run([sys.executable, __file__, "--worker", str(build)],
                             capture_output=True, text=True, check=True)
        children.append(json.loads(run.stdout))
    first, second = children
    if first["mapped_router"] == second["mapped_router"] or first["router_sha256"] == second["router_sha256"]:
        raise RuntimeError("differential did not load distinct router implementations")
    differences = []
    maxima = {key: 0.0 for key in sorted(FLOAT_FIELDS)}
    for a, b in zip(first["records"], second["records"], strict=True):
        for key in ("case", "shape", "seed", "input_sha256", "return_code", "router_calls_in_worker"):
            if a[key] != b[key]: differences.append((a["case"], a["seed"], key, a[key], b[key]))
        for key in a["fields"]:
            x, y = a["fields"][key], b["fields"][key]
            if not same(x, y): differences.append((a["case"], a["seed"], key, x, y))
            if key in FLOAT_FIELDS and isinstance(x, float) and isinstance(y, float):
                maxima[key] = max(maxima[key], abs(x - y))
        for key in a["router_meta"]:
            x, y = a["router_meta"][key], b["router_meta"][key]
            if not (x == y if key in ROUTER_INTEGERS else same(x, y)):
                differences.append((a["case"], a["seed"], "router." + key, x, y))
        for key in a["diagnostics"]:
            x, y = a["diagnostics"][key], b["diagnostics"][key]
            if key == "core_rank_interval":
                equal = x == y
            else:
                equal = same(x, y)
            if not equal: differences.append((a["case"], a["seed"], key, x, y))
    data = {"method": "separate process per build; one mapped router DSO each",
            "float_tolerance": "abs<=1e-12 or rel<=1e-12; exact integer and sentinel comparison",
            "baseline": first, "candidate": second, "max_abs_delta": maxima,
            "differences": differences}
    output.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(f"{len(first['records'])} cases compared; {len(differences)} differences; raw: {output}")
    for difference in differences[:20]: print("DIFF", difference)
    return bool(differences)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        print(json.dumps(worker(Path(sys.argv[2])), sort_keys=True, allow_nan=False))
    elif len(sys.argv) == 4:
        sys.exit(parent(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])))
    else:
        raise SystemExit(__doc__)
