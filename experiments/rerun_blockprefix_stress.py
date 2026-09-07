#!/usr/bin/env python3
import os;os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','4')
import ctypes,json,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];DP=ctypes.POINTER(ctypes.c_double)
L=ctypes.CDLL(str(ROOT/'libaffine_bundle_solver.so'))
L.bsolve_router_meta_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulonglong,ctypes.c_int,DP]
L.bsolve_fg_counters_reset_api.argtypes=[];L.bsolve_fg_counters_api.argtypes=[ctypes.POINTER(ctypes.c_ulonglong)]
def p(a):return a.ctypes.data_as(DP)
def call(A,b,x,seed):
 o=np.zeros(11);L.bsolve_router_meta_api(p(A),p(b),p(x),A.shape[0],A.shape[1],1,2,2,seed,0,p(o));return o
def mk(m,n,r,seed,cancel=False):
 rng=np.random.default_rng(seed);B=np.zeros((r,n));B[:,:r]=np.eye(r)
 if r<n:B[:,r:]=rng.integers(-2,3,size=(r,n-r))
 U=rng.integers(-3,4,size=(m,r)).astype(float);U[:r,:]=np.eye(r)
 if cancel and m>2*r:
  q=min((m-r)//2,100)
  for t in range(q):
   v=rng.integers(-3,4,size=r).astype(float);U[r+2*t]=v;U[r+2*t+1]=-v
 A=np.ascontiguousarray(U@B);x=rng.integers(-2,3,size=n).astype(float);b=np.ascontiguousarray(A@x);return A,b,x
rows=[];wrong=[];L.bsolve_fg_counters_reset_api();t0=time.perf_counter()
for r in [4,8,32,96,191]:
 for cancel in [False,True]:
  A,b,x=mk(512,192,r,100+r+1000*cancel,cancel);bad=[];times=[]
  for seed in range(1,101):
   o=call(A,b,x,seed);times.append(float(o[7]))
   if int(o[0])!=2 or int(o[2])!=r:bad.append({'seed':seed,'status':int(o[0]),'rank':int(o[2]),'lo':int(o[3]),'hi':int(o[4])})
  rows.append({'r':r,'cancellation':cancel,'checks':100,'wrong':bad,'median_ms':float(np.median(times)*1e3)})
  wrong.extend([{'r':r,'cancellation':cancel,**z} for z in bad]);print(rows[-1],flush=True)
c=(ctypes.c_ulonglong*3)();L.bsolve_fg_counters_api(c)
out={'checks':1000,'hard_failures':len(wrong),'failures':wrong,'formation_guard_checks':int(c[0]),'formation_escalations':int(c[1]),'source_qrcp_calls':int(c[2]),'elapsed_s':time.perf_counter()-t0,'rows':rows}
(ROOT/'results/blockprefix_final_1000.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:out[k] for k in out if k!='rows' and k!='failures'},indent=2))
