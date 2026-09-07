#!/usr/bin/env python3
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','4')
import ctypes, json, time
from pathlib import Path
import numpy as np
from scipy.io import mmread
from scipy.linalg import lstsq
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
DP=ctypes.POINTER(ctypes.c_double)
L=ctypes.CDLL(str(ROOT/'libaffine_bundle_solver.so'))
L.bsolve_router_meta_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulonglong,ctypes.c_int,DP]

def p(x): return x.ctypes.data_as(DP)
def call(A,b,x,seed=777,reps=7):
    A=np.ascontiguousarray(A,float); b=np.ascontiguousarray(b,float); x=np.ascontiguousarray(x,float)
    ts=[]; outs=[]
    for _ in range(reps):
        o=np.zeros(11); t=time.perf_counter()
        L.bsolve_router_meta_api(p(A),p(b),p(x),len(b),A.shape[1],1,2,2,seed,0,p(o))
        ts.append(time.perf_counter()-t); outs.append(o.copy())
    k=int(np.argsort(ts)[len(ts)//2]); o=outs[k]
    return {'ms':1000*ts[k],'status':int(o[0]),'certainty':int(o[1]),'rank':int(o[2]),
            'lo':int(o[3]),'hi':int(o[4]),'rr':None if not np.isfinite(o[5]) else float(o[5]),
            'rx':None if not np.isfinite(o[6]) else float(o[6]),
            'eta_x':None if not np.isfinite(o[10]) else float(o[10])}

def lap(A,b,reps=5):
    ts=[]; z=None
    with threadpool_limits(limits=1,user_api='blas'):
        for _ in range(reps):
            t=time.perf_counter(); x,res,rank,s=lstsq(np.array(A,order='F'),b,cond=1e-10,lapack_driver='gelsy',check_finite=False)
            ts.append(time.perf_counter()-t); z=(x,rank)
    x,rank=z; rr=np.linalg.norm(A@x-b)/(np.linalg.norm(b)+1e-300)
    return {'ms':1000*float(np.median(ts)),'rank':int(rank),'rr':float(rr)}

A=mmread(DATA/'well1033.mtx').toarray().astype(float)
rhs=np.asarray(mmread(DATA/'well1033_rhs1.mtx')).ravel().astype(float)
out={'shape':list(A.shape),'nnz':int(np.count_nonzero(A)),'cond2':float(np.linalg.cond(A))}
rows=[]
with threadpool_limits(limits=1,user_api='blas'):
    for sx in [1,2,3,4,20260812]:
        rng=np.random.default_rng(sx); x=rng.standard_normal(A.shape[1]); b=A@x
        rows.append({'seed':sx,'router':call(A,b,x),'dgel_sy':lap(A,b)})
out['constructed_rhs_stress']=rows
out['consistent']=rows[-1]
z=np.zeros(A.shape[1])
out['published_rhs']={'router':call(A,rhs,z),'dgel_sy':lap(A,rhs)}
path=ROOT/'results/well1033_reviewed.json'; path.write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
