"""Saved triples, isolated libraries, warmed alternating single-core certificate timings."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "ABS_CERT_UNIQUE_THREADS"):
    os.environ[var] = "1"

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"tests"))
import api_regression_binding as api

# Fixed generator seeds; each saved x is produced once, by BASE.
CASES = {
    "w1":(96,512,8031),"w2":(128,768,8032),"w3":(256,2048,8033),
    "t1":(1024,16,8101),"t2":(2048,32,8102),"t3":(4096,48,8103),
    "extreme":(32,12800,8004),"square":(96,96,8005),"grouped":(512,32,8006),
    "grey":(32,192,8007),"defect":(96,512,8008),"conflict":(128,16,8009),
    "wh1":(112,608,8191),"wh2":(192,1344,8192),
    "th1":(1536,24,8193),"th2":(3072,40,8194),
}

def generate(base, folder, names):
    folder.mkdir(exist_ok=True, parents=True)
    lib=api.load_library(Path(base))
    for name in names:
        m,n,seed=CASES[name]
        rng=np.random.default_rng(seed)
        A=rng.standard_normal((m,n))
        if name=="grouped":
            A=np.repeat(A[:n],m//n,axis=0)
        if name in ("defect","grey"):
            A[-1]=A[0]+(1e-10 if name=="grey" else 0.0)*A[-1]
        b=A@rng.standard_normal(n)
        if name=="conflict":
            b[-1]+=1
        rc,x,_=api.invoke_solve(lib,A,b,api.default_policy(lib))
        assert rc==0
        np.savez(folder/(name+".npz"),A=A,b=b,x=x)

def measure(lib, path, trace=False):
    with np.load(path) as data:
        A,b,x=(data[k] for k in ("A","b","x"))
    out=api.CandidateCertificateResult()
    lib.bs_init_certificate_result(ctypes.byref(out))
    ptr=lambda v:v.ctypes.data_as(api.DP)
    args=(ptr(A),ptr(b),ptr(x),*A.shape,ctypes.byref(out))
    call=lib.bs_certify_candidate
    if call(*args):
        raise RuntimeError(path)
    if trace:
        os.environ["RALPH_TRACE"]="1"
    times=[]
    batch=2 if A.size<100000 else 1
    for _ in range(3):
        start=time.perf_counter_ns()
        for _ in range(batch):
            rc=call(*args)
        times.append((time.perf_counter_ns()-start)/batch/1e6)
        if rc:
            raise RuntimeError((path,rc))
    os.environ.pop("RALPH_TRACE",None)
    fields={k:(v.hex() if isinstance(v,float) else v) for k,_ in out._fields_
            for v in (getattr(out,k),)}
    return dict(ms=times,batch=batch,result=fields,
                hashes=[hashlib.sha256(v).hexdigest() for v in (A,b,x)])

def summarize(blocks):
    rng=np.random.default_rng(42)
    idx=rng.integers(len(blocks),size=(5000,len(blocks)))
    summary={}
    samples=[]
    for name in blocks[0]["base"]:
        for row in blocks:
            a,b=[row[k][name] for k in ("base","new")]
            assert a["result"]==b["result"] and a["hashes"]==b["hashes"],(name,a,b)
        a,b=[np.array([statistics.median(row[k][name]["ms"]) for row in blocks])
             for k in ("base","new")]
        ratio=b/a
        boot=np.median(b[idx],axis=1)/np.median(a[idx],axis=1)
        samples.append(boot)
        summary[name]=dict(base=np.median(a),new=np.median(b),ratio=np.median(b)/np.median(a),
                           mad=np.median(abs(ratio-np.median(ratio))),
                           ci=np.quantile(boot,[.025,.975]).tolist())
    gm=np.exp(np.mean([np.log(s["ratio"]) for s in summary.values()]))
    ci=np.quantile(np.exp(np.mean(np.log(samples),axis=0)),[.025,.975])
    return dict(cases=summary,geomean=gm,ci=ci.tolist())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("base",type=Path)
    ap.add_argument("new",type=Path)
    ap.add_argument("output",type=Path)
    ap.add_argument("cases",nargs="+",choices=CASES)
    ap.add_argument("--inputs",type=Path,default=HERE/"inputs")
    ap.add_argument("--generate",action="store_true")
    ap.add_argument("--worker",action="store_true")
    ap.add_argument("--trace",action="store_true")
    ap.add_argument("--blocks",type=int,default=8)
    opts=ap.parse_args()
    if opts.generate:
        generate(opts.base,opts.inputs,opts.cases)
        return
    if opts.worker:
        lib=api.load_library(opts.base)
        print(json.dumps({name:measure(lib,opts.inputs/(name+".npz"),opts.trace) for name in opts.cases}))
        return
    blocks=[]
    for i in range(opts.blocks):
        row={}
        for side in (("base","new") if i%2==0 else ("new","base")):
            cmd=[sys.executable,__file__,str(getattr(opts,side)),"-","-",*opts.cases,
                 "--worker","--inputs",str(opts.inputs)]
            row[side]=json.loads(subprocess.check_output(cmd))
        blocks.append(row)
    result=summarize(blocks)
    opts.output.write_text(json.dumps(dict(summary=result,blocks=blocks),indent=1)+"\n")
    print(json.dumps(result))

if __name__=="__main__":
    main()
