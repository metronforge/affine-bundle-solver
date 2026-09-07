import ctypes, math
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
lib=ctypes.CDLL(str(ROOT/'libcertified_solver.so'))

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
lib.bsolve_certified_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,
                                   ctypes.c_ulonglong,ctypes.c_int,ctypes.POINTER(Result)]
lib.bsolve_certified_api.restype=ctypes.c_int

def dp(a): return np.ascontiguousarray(a,dtype=np.float64).ctypes.data_as(DP)
def call(A,b,x):
    A=np.ascontiguousarray(A,dtype=np.float64);b=np.ascontiguousarray(b,dtype=np.float64);x=np.ascontiguousarray(x,dtype=np.float64)
    r=Result();rc=lib.bsolve_certified_api(dp(A),dp(b),dp(x),A.shape[0],A.shape[1],1,2,2,12345,0,ctypes.byref(r))
    assert rc==0
    return r

rng=np.random.default_rng(7)
# Unique: tall, full column rank, exactly compatible.
A=rng.standard_normal((48,8));x=rng.standard_normal(8);b=A@x
r=call(A,b,x);assert r.fast_status==1,(r.fast_status,r.rank_estimate);assert r.certified_status==1,(r.generator_code,r.verifier_code,r.eta_status);assert math.isfinite(r.eta_status)
assert r.accepted_status_mask & 1; assert r.eta_status == r.eta_unique
print('unique',r.eta_status,'profile',r.eta_unique,r.eta_infinite,r.eta_inconsistent)

# Infinite: exact rank 6 < 8, compatible.
C=rng.standard_normal((48,6));V=rng.standard_normal((6,8));A=C@V;x=rng.standard_normal(8);b=A@x
r=call(A,b,x);assert r.fast_status==2,(r.fast_status,r.rank_estimate,r.rank_lo,r.rank_hi);assert r.certified_status==2,(r.generator_code,r.verifier_code,r.eta_status);assert math.isfinite(r.eta_status)
assert r.accepted_status_mask & 2; assert r.eta_status == r.eta_infinite
print('infinite',r.eta_status,'profile',r.eta_unique,r.eta_infinite,r.eta_inconsistent)

# Inconsistent: rank-deficient tall system with a source contradiction.
C=rng.standard_normal((48,6));V=rng.standard_normal((6,8));A=C@V;x=rng.standard_normal(8);b=A@x;b[-1]+=1e-3*max(1.0,np.linalg.norm(A[-1]))
r=call(A,b,x);assert r.fast_status==3,(r.fast_status,r.rank_estimate,r.rank_lo,r.rank_hi);assert r.certified_status==3,(r.generator_code,r.verifier_code,r.eta_status);assert math.isfinite(r.eta_status)
assert r.accepted_status_mask & 4; assert r.eta_status == r.eta_inconsistent
print('inconsistent',r.eta_status,'profile',r.eta_unique,r.eta_infinite,r.eta_inconsistent)
print('PASS')
