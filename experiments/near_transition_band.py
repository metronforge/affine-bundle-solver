#!/usr/bin/env python3
"""
near_transition_band.py -- where the threshold insertion path and the
certified path disagree.

bsolve_seq_api is the loop over bs_insert, which decides by a single
threshold and therefore always produces a verdict.  The router reaches the
same data through bs_insert_certified, which carries an explicit band in
which it declines to decide.  This script measures the width of that band on
a family that walks across a rank transition.

The output backs section 2 of docs/incremental-api-proposal.md.  Run it from
the repository root after build.sh.
"""
import ctypes, numpy as np
DP=ctypes.POINTER(ctypes.c_double)
lib=ctypes.CDLL("./libaffine_bundle_solver.so")
lib.bsolve_seq_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,DP]
lib.bsolve_router_meta_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,ctypes.c_int,
    ctypes.c_int,ctypes.c_int,ctypes.c_ulonglong,ctypes.c_int,DP]
p=lambda a: np.ascontiguousarray(a,dtype=np.float64).ctypes.data_as(DP)
CLS={1:"UNIQUE",2:"INFINITE",3:"INCONSISTENT",4:"FAIL",5:"UNDECIDABLE"}
rng=np.random.default_rng(11)
m,n=1500,12
base=rng.standard_normal((m,n))
print("  Last column = first * (1 + eps*sin i).  seq threshold: 1e-10.")
print("  Refusal band of the certified path: [1e-13, 1e-9].\n")
print(f"  {'eps':>8s} {'seq (bs_insert)':>16s} {'router':>14s}  {'rank seq/router':>16s}")
print("  "+"-"*62)
for e in [0,1e-15,1e-14,1e-13,1e-12,1e-11,1e-10,1e-9,1e-8,1e-6]:
    A=base.copy(); A[:,-1]=A[:,0]*(1.0+e*np.sin(np.arange(m)))
    x=rng.standard_normal(n); b=A@x
    o1=np.zeros(7); lib.bsolve_seq_api(p(A),p(b),p(x),m,n,p(o1))
    o2=np.zeros(11); lib.bsolve_router_meta_api(p(A),p(b),p(x),m,n,1,2,2,12345,0,p(o2))
    s1,s2=CLS.get(int(o1[0]),"?"),CLS.get(int(o2[9]),"?")
    mark="  <-- disagree" if s1!=s2 else ""
    print(f"  {e:>8.0e} {s1:>16s} {s2:>14s}  {int(o1[1]):>7d}/{int(o2[2]):<7d}{mark}")
