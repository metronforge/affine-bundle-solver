"""Paired, process-isolated bsolve benchmark. Run with Python 3 from any cwd."""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[variable] = "1"
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tests"))
import api_regression_binding as api

# name, m, n, seed. Holdouts are generated on demand only.
CASES = {
    "w1": (96, 512, 301), "w2": (128, 768, 302), "w3": (256, 2048, 303),
    "extreme": (32, 12800, 304), "tall": (8000, 32, 305),
    "grouped": (2048, 64, 306), "square": (192, 192, 307),
    "grey": (32, 192, 308), "small": (48, 192, 309),
    "defect": (96, 512, 310), "conflict": (96, 512, 311),
    "ill": (96, 512, 312), "grey2": (96, 512, 313),
    "hold1": (112, 608, 7301), "hold2": (192, 1344, 7302),
}
PRIMARY = ["w1", "w2", "w3"]
CONTROLS = ["extreme", "tall", "grouped", "square", "grey", "small"]

def inputs(name, cache):
    path = cache / (name + ".npz")
    if not path.exists():
        m, n, seed = CASES[name]
        rng = np.random.default_rng(seed)
        A = rng.standard_normal((m, n))
        if name == "grouped":
            A = np.repeat(A[:n], m // n, axis=0)
        if name in ("grey", "grey2", "ill"):
            A[-1] = A[0] + (1e-10 if name != "ill" else 1e-8) * A[-1]
        if name in ("defect", "conflict"):
            A[-1] = A[0]
        b = A @ rng.standard_normal(n)
        if name == "conflict":
            b[-1] += 1
        cache.mkdir(exist_ok=True, parents=True)
        np.savez(path, A=A, b=b)
    with np.load(path) as f:
        return f["A"], f["b"]

def measurement(lib, name, cache, repeats):
    A, b = inputs(name, cache)
    ptr = lambda a: a.ctypes.data_as(api.DP)
    x = np.empty(A.shape[1])
    p = api.default_policy(lib)
    out = api.OperationalResult()
    lib.bs_init_solve_result(C.byref(out))
    args = (ptr(A), ptr(b), *A.shape, C.byref(p), ptr(x), C.byref(out))
    call = lib.bsolve
    if call(*args):
        raise RuntimeError(name)
    batch = 12 if name in ("grey", "small", "grouped", "square") else 2
    times = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(batch):
            rc = call(*args)
        times.append((time.perf_counter_ns() - start) / batch / 1e6)
        if rc:
            raise RuntimeError(name)
    rc, check = api.invoke_candidate_check(lib, A, b, x, p)
    if rc:
        raise RuntimeError("candidate check")
    meta = list(out.router_meta)
    return dict(ms=times, batch=batch, policy=p.values(), status=out.operational_status,
                certainty=out.operational_certainty, rank=meta[2:5], exact=[out.exact_source_status,
                out.exact_source_verification], guards=list(out.formation_guard_counters),
                core=out.core_qr_rank, grey=out.grey_total_events, fallback=meta[8],
                x=hashlib.sha256(x.tobytes()).hexdigest(), check=check.verdict,
                berr=check.mixed_backward_error_up, input=hashlib.sha256(
                    memoryview(A).cast("B")).hexdigest(), rhs=hashlib.sha256(b).hexdigest())

def summary(blocks):
    result = {}
    rng = np.random.default_rng(42)
    indices = rng.integers(len(blocks), size=(4000, len(blocks)))
    for name in blocks[0]["base"]:
        base, new = (np.array([statistics.median(b[side][name]["ms"])
                               for b in blocks]) for side in ("base", "new"))
        ratios = new / base
        boot = np.median(new[indices], axis=1) / np.median(base[indices], axis=1)
        same = all(all(b["base"][name][key] == b["new"][name][key] for key in
                       ("input","rhs","policy","status","certainty","rank","exact","x","check","berr"))
                   for b in blocks)
        result[name] = dict(base=np.median(base), new=np.median(new),
                            ratio=np.median(new)/np.median(base),
                            mad=np.median(abs(ratios-np.median(ratios))),
                            ci=np.quantile(boot,[.025,.975]).tolist(), same=same)
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("new")
    ap.add_argument("output")
    ap.add_argument("cases", nargs="+", choices=CASES)
    ap.add_argument("--blocks", type=int, default=8)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--cache", type=Path, default=Path("/tmp/ralph-inputs"))
    ap.add_argument("--worker", action="store_true")
    opts = ap.parse_args()
    if opts.worker:
        lib = api.load_library(Path(opts.base))
        print(json.dumps({n: measurement(lib,n,opts.cache,opts.repeats) for n in opts.cases}))
        return
    blocks = []
    for i in range(opts.blocks):
        block = {}
        for side in (("base","new") if i % 2 == 0 else ("new","base")):
            cmd = [sys.executable, __file__, getattr(opts,side), "-", "-", *opts.cases,
                   "--cache",str(opts.cache),"--repeats",str(opts.repeats),"--worker"]
            block[side] = json.loads(subprocess.check_output(cmd))
        blocks.append(block)
    result = summary(blocks)
    Path(opts.output).write_text(json.dumps(dict(blocks=blocks, summary=result),indent=1)+"\n")
    for name,s in result.items():
        print(name, *(round(s[k],4) for k in ("base","new","ratio","mad")),s["same"])

if __name__ == "__main__":
    main()
