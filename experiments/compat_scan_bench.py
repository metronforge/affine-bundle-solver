#!/usr/bin/env python3
"""Build/freeze real-router probes and compare scan + public API timings.

Run build at each committed experimental revision before changing source.
No source copies or patched solver sources are created in build directories.
"""
import argparse
import ctypes as ct
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shlex
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "BLIS_NUM_THREADS")


def run(args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(args):
    dest = Path(args.directory).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    if run(["git", "status", "--porcelain"], cwd=ROOT):
        raise SystemExit("Commit the source before freezing a build")
    identity = {"repository": str(ROOT), "branch": run(["git", "branch", "--show-current"], cwd=ROOT),
                "commit": run(["git", "rev-parse", "HEAD"], cwd=ROOT),
                "tree": run(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT), "dirty": False}
    configure = ["cmake", "-S", str(ROOT), "-B", str(dest), "-DABS_BLAS=scipy-openblas",
                 "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON", "-DABS_BUILD_EXAMPLES=OFF",
                 "-DABS_DISABLE_ROUTER_AUTOVECTORIZATION=" + ("ON" if args.scalar else "OFF")]
    subprocess.run(configure, check=True)
    subprocess.run(["cmake", "--build", str(dest), "-j2"], check=True)
    commands = json.loads((dest / "compile_commands.json").read_text())
    router = next(c for c in commands if "abs_router_obj.dir" in c["command"])
    compile_argv = shlex.split(router["command"])
    compile_argv[compile_argv.index("-o") + 1] = str(dest / "compat_probe.o")
    compile_argv[compile_argv.index("-c") + 1] = str(ROOT / "experiments/compat_scan_probe.c")
    compile_argv.append("-fopt-info-vec-all=" + str(dest / "probe-vectorization.txt"))
    subprocess.run(compile_argv, check=True, cwd=dest)
    link = shlex.split((dest / "CMakeFiles/affine_bundle_solver.dir/link.txt").read_text())
    link = [str(dest / "compat_probe.o") if s.endswith("abs_router_obj.dir/src/bsolver.c.o") else s for s in link]
    link[link.index("-o") + 1] = str(dest / "libcompat_probe.so")
    # Bind internal calls within this diagnostic library, avoiding interposition
    # when several variants are compared in one process. Production is unmodified.
    link.append("-Wl,-Bsymbolic")
    subprocess.run(link, check=True, cwd=dest)
    with (dest / "probe-assembly.txt").open("w") as stream:
        subprocess.run(["objdump", "-d", "-Mintel", str(dest / "compat_probe.o")], stdout=stream, check=True)
    import scipy
    blas = next((Path(scipy.__file__).parent.parent / "scipy.libs").glob("libscipy_openblas*.so"))
    identity.update(configure=configure, probe_compile=compile_argv, probe_link=link,
                    compiler=run(["gcc", "--version"]), machine=platform.platform(),
                    cpu=run(["lscpu"]), blas={"path": str(blas), "sha256": sha(blas)},
                    binaries={str(p.relative_to(dest)): sha(p) for p in dest.glob("*.so")},
                    strict_objects={c["file"]: sha(dest / shlex.split(c["command"])[shlex.split(c["command"]).index("-o")+1])
                                    for c in commands if any(t in c["command"] for t in
                                        ("abs_formation_guard_obj.dir", "status_verifier.dir", "certified_solver.dir"))},
                    compile_commands=commands)
    (dest / "freeze.json").write_text(json.dumps(identity, indent=2) + "\n")


def load(directory):
    import numpy as np
    dp = np.ctypeslib.ndpointer(dtype=np.float64, flags="C_CONTIGUOUS")
    directory = Path(directory).resolve()
    freeze = json.loads((directory / "freeze.json").read_text())
    for p, expected in freeze["binaries"].items():
        assert sha(directory / p) == expected, (directory, p, "binary changed")
    probe = ct.CDLL(str(directory / "libcompat_probe.so"))
    probe.abs_compat_scan_probe.argtypes = [dp, dp, dp, ct.c_int, ct.c_int, ct.c_double, dp]
    probe.abs_compat_scan_probe.restype = None
    router = ct.CDLL(str(directory / "libaffine_bundle_solver.so"))
    router.bsolve_router_meta_api.argtypes = [dp, dp, ct.c_void_p] + [ct.c_int]*5 + [ct.c_ulonglong, ct.c_int, dp]
    router.bsolve_router_meta_api.restype = None
    router.bsolve_router_api.argtypes = router.bsolve_router_meta_api.argtypes
    router.bsolve_router_api.restype = None
    router.bsolve_fg_counters_reset_api.argtypes = []
    router.bsolve_fg_counters_reset_api.restype = None
    router.bsolve_fg_counters_api.argtypes = [ct.POINTER(ct.c_ulonglong)]
    router.bsolve_fg_counters_api.restype = None
    return probe, router, freeze


def summary(values):
    med = statistics.median(values)
    return dict(median=med, mad=statistics.median(abs(v-med) for v in values),
                minimum=min(values), maximum=max(values), raw=values)


def bench(args):
    for key in THREADS:
        if os.environ.get(key) != "1":
            raise SystemExit(f"Set {key}=1 before starting Python")
    import numpy as np
    from synthetic_bench import gen_tall
    os.sched_setaffinity(0, {args.cpu})
    libs = dict((label, load(path)) for label, path in (s.split("=", 1) for s in args.variant))
    shapes = [(int(m), int(n)) for m, n in (s.split("x") for s in args.shapes.split(","))]
    result = dict(protocol=dict(repeats=args.repeats, warmups=3, cpu=args.cpu,
                                threads={k: os.environ[k] for k in THREADS}, seed=20260929,
                                interleave="randomized variant order each round", shapes=shapes),
                  builds={label: v[2] for label, v in libs.items()}, cases=[])
    for m, n in shapes:
        rng = np.random.default_rng(20260929 + n + m)
        a, _, _ = gen_tall(rng, m, n)
        x = np.ascontiguousarray(rng.standard_normal(n))
        b = np.ascontiguousarray(a @ x)
        case = dict(m=m, n=n, branch="an2" if n>=192 else "amax",
                    input_sha256=hashlib.sha256(a.tobytes()+b.tobytes()+x.tobytes()).hexdigest())
        for mode in ("scan", "router"):
            outs = {k: np.zeros(5 if mode=="scan" else 11) for k in libs}
            times = {k: [] for k in libs}
            order_rng = random.Random(20260929)
            decisions = {k: set() for k in libs}
            for repeat in range(args.repeats+3):
                order = list(libs)
                order_rng.shuffle(order)
                for label in order:
                    probe, router, _ = libs[label]
                    t = time.perf_counter()
                    if mode == "scan":
                        probe.abs_compat_scan_probe(a,b,x,m,n,2e-10,outs[label])
                        semantic = outs[label][[0,3,4]]
                    else:
                        router.bsolve_router_meta_api(a,b,None,m,n,1,2,2,20260909,0,outs[label])
                        semantic = outs[label][[0,1,2,3,4,8,9]]
                    elapsed = time.perf_counter()-t
                    decisions[label].add(tuple(semantic))
                    if repeat>=3:
                        times[label].append(elapsed)
            case[mode] = {k: dict(**summary(times[k]), output=outs[k].tolist(),
                                   decisions=[list(d) for d in sorted(decisions[k])]) for k in libs}
        result["cases"].append(case)
        # Untimed existing diagnostics: the public fallback field alone does
        # not expose all quality-repair/source-QRCP work.
        case["route_trace"] = {}
        for label, (_, router, _) in libs.items():
            out = np.zeros(11)
            counters = (ct.c_ulonglong*3)()
            router.bsolve_fg_counters_reset_api()
            router.bsolve_router_meta_api(a,b,None,m,n,1,2,2,20260909,0,out)
            router.bsolve_fg_counters_api(counters)
            raw = np.zeros(7)
            router.bsolve_router_api(a,b,None,m,n,1,2,2,20260909,0,raw)
            case["route_trace"][label] = dict(formation_checks=counters[0],
                formation_escalations=counters[1], source_qrcp_calls=counters[2],
                raw_class=raw[0], raw_rank=raw[1], fallback=raw[2], accepted_random=raw[3])
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
        print(m,n,{mode:{k:round(case[mode][k]["median"]*1000,3) for k in libs} for mode in ("scan","router")},flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="mode", required=True)
    b = sub.add_parser("build")
    b.add_argument("directory")
    b.add_argument("--scalar", action="store_true")
    b.set_defaults(func=build)
    b = sub.add_parser("bench")
    b.add_argument("--variant", action="append", required=True, help="label=build-directory")
    b.add_argument("--shapes", default="131072x32,131072x64,65536x128,65536x191,65536x192,65536x193,32768x256,16384x512")
    b.add_argument("--repeats", type=int, default=15)
    b.add_argument("--cpu", type=int, default=0)
    b.add_argument("--output", required=True)
    b.set_defaults(func=bench)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
