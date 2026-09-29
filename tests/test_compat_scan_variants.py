#!/usr/bin/env python3
"""Differential semantics for committed compat-scan experimental builds.

Checks decisions separately from floating diagnostics, and records exact-boundary
disagreements rather than adjusting tolerances. --variant baseline=DIR is required.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from compat_scan_bench import load


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--variant", action="append", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    libs = {k: load(v) for k, v in (s.split("=", 1) for s in args.variant)}
    assert "baseline" in libs
    rng = np.random.default_rng(728113)
    report = dict(cases=0, disagreements=[], diagnostic_differences={k:0 for k in libs},
                  sources={k:v[2]["commit"] for k,v in libs.items()})

    def check(a,b,x,tag,boundary=False, expected=None):
        # Deliberately 8-byte offset: no 32-byte API alignment assumption.
        storage = np.empty(a.size+1)
        storage[1:] = a.ravel()
        a = storage[1:].reshape(a.shape)
        b,x = np.ascontiguousarray(b),np.ascontiguousarray(x)
        values = {}
        for k,(probe,_,_) in libs.items():
            out = np.zeros(5)
            probe.abs_compat_scan_probe(a,b,x,*a.shape,2e-10,out)
            values[k] = out.tolist()
        ref = values["baseline"]
        if expected is not None:
            assert ref[0] == expected, (tag,ref)
        for k,val in values.items():
            if val[0]!=ref[0] or val[3:]!=ref[3:]:
                report["disagreements"].append(dict(variant=k,case=tag,boundary=boundary,
                                                     baseline=ref,actual=val))
            if not np.array_equal(np.array(val)[1:3],np.array(ref)[1:3],equal_nan=True):
                report["diagnostic_differences"][k]+=1
        report["cases"]+=1

    for n in (1,3,7,31,32,63,64,95,127,128,190,191,192,193,194,255,256,383,384,512):
        for scale in (1e-200,1e-150,1.0,1e150,1e200):
            a = rng.standard_normal((7,n))*scale
            x = rng.standard_normal(n)
            b = np.asarray(a.astype(np.longdouble) @ x.astype(np.longdouble), dtype=np.float64)
            check(a,b,x,f"compatible/n={n}/scale={scale}",expected=0)
            a[0]=0;b[0]=0
            check(a,b,x,f"zero-row/n={n}/scale={scale}",expected=0)
            b[0]=1.0
            check(a,b,x,f"zero-contradiction/n={n}/scale={scale}",expected=1)
        for seed in range(12):
            a = rng.standard_normal((1,n))
            x = rng.standard_normal(n)
            dot = (a.astype(np.longdouble) @ x.astype(np.longdouble)).item()
            dot = float(dot)
            an,xn = np.linalg.norm(a),np.linalg.norm(x)
            for kind,t,den in (("compat",2e-10,an*(1+xn)),("quality",1e-14,an*xn)):
                # Positive residual above a nonnegative dot so |b| has no kink.
                if dot<0:
                    a=-a;dot=-dot
                delta=t*(dot+den)/(1-t)
                for factor in (0.5,0.99,1.0,1.01,2.0):
                    b=np.array([dot+factor*delta])
                    check(a,b,x,f"{kind}/n={n}/seed={seed}/factor={factor}",boundary=factor==1.0)
    Path(args.output).write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="disagreements"},indent=2))
    counts = {k:sum(d["variant"]==k for d in report["disagreements"]) for k in libs}
    print("Decision disagreements:",counts)
    print("Away from exact boundary:",{k:sum(d["variant"]==k and not d["boundary"] for d in report["disagreements"]) for k in libs})


if __name__ == "__main__":
    main()
