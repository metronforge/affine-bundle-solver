#!/usr/bin/env python3
import argparse, ctypes, json, statistics, time
from pathlib import Path
import numpy as np

class Result(ctypes.Structure):
    _fields_=[('fast_status',ctypes.c_int),('fast_certainty',ctypes.c_int),
              ('rank_estimate',ctypes.c_int),('rank_lo',ctypes.c_int),('rank_hi',ctypes.c_int),
              ('eta_x',ctypes.c_double),('certified_status',ctypes.c_int),
              ('eta_status',ctypes.c_double),('generator_code',ctypes.c_int),('verifier_code',ctypes.c_int),
              ('accepted_status_mask',ctypes.c_int),('eta_unique',ctypes.c_double),('eta_infinite',ctypes.c_double),('eta_inconsistent',ctypes.c_double),
              ('unique_generator_code',ctypes.c_int),('unique_verifier_code',ctypes.c_int),
              ('infinite_generator_code',ctypes.c_int),('infinite_verifier_code',ctypes.c_int),
              ('inconsistent_generator_code',ctypes.c_int),('inconsistent_verifier_code',ctypes.c_int)]
DP=ctypes.POINTER(ctypes.c_double)

def arr(x): return np.ascontiguousarray(x,dtype=np.float64)
def ptr(x): return x.ctypes.data_as(DP)

def exact_family(m,n,r,inconsistent,seed):
    rng=np.random.default_rng(seed)
    # Small integer factors give an exactly rank-at-most-r stored construction.
    U=rng.integers(-3,4,size=(m,r),dtype=np.int64).astype(np.float64)
    V=rng.integers(-3,4,size=(r,n),dtype=np.int64).astype(np.float64)
    A=arr(U@V)
    x=arr(rng.integers(-2,3,size=n).astype(np.float64))
    b=arr(A@x)
    if inconsistent:
        # Append contradiction in a left-null direction constructed by duplicating
        # the final row before changing only its rhs.
        if m>=2:
            A[-1]=A[-2]
            b[-1]=b[-2]+1.0
    return A,b,x

def full_rank_family(m,n,seed):
    rng=np.random.default_rng(seed)
    A=np.zeros((m,n),dtype=np.float64)
    A[:n,:]=np.eye(n)
    if m>n:
        A[n:]=rng.integers(-2,3,size=(m-n,n),dtype=np.int64)
    x=rng.integers(-2,3,size=n,dtype=np.int64).astype(np.float64)
    return arr(A),arr(A@x),arr(x)

def run(root,reps):
    root=Path(root)
    lib=ctypes.CDLL(str(root/'libcertified_solver.so'))
    lib.bsolve_certified_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,
                                       ctypes.c_ulonglong,ctypes.c_int,ctypes.POINTER(Result)]
    lib.bsolve_certified_api.restype=ctypes.c_int
    cases=[]
    specs=[(128,32),(512,64),(2048,64)]
    for q,(m,n) in enumerate(specs):
        cases.append((f'compatible_full_{m}x{n}',)+full_rank_family(m,n,100+q))
        A,b,x=exact_family(m,n,max(1,n//2),True,200+q)
        cases.append((f'inconsistent_rank{n//2}_{m}x{n}',A,b,x))
    out=[]
    for name,A,b,x in cases:
        def one():
            rr=Result(); rc=lib.bsolve_certified_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],1,2,2,12345,0,ctypes.byref(rr))
            if rc: raise RuntimeError((name,rc))
            return rr
        for _ in range(2): one()
        tt=[]; last=None
        for _ in range(reps):
            t0=time.perf_counter_ns(); last=one(); tt.append((time.perf_counter_ns()-t0)/1e6)
        out.append({'case':name,'m':A.shape[0],'n':A.shape[1],
                    'median_ms':statistics.median(tt),'min_ms':min(tt),'max_ms':max(tt),
                    'mask':int(last.accepted_status_mask),'eta_inconsistent':float(last.eta_inconsistent),
                    'inc_codes':[int(last.inconsistent_generator_code),int(last.inconsistent_verifier_code)]})
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); ap.add_argument('--reps',type=int,default=9); ap.add_argument('--output',required=True); a=ap.parse_args()
    out={'root':str(Path(a.root).resolve()),'reps':a.reps,'cases':run(a.root,a.reps)}
    Path(a.output).write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2))
if __name__=='__main__': main()
