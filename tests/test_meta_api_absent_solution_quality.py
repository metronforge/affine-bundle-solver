#!/usr/bin/env python3
import os
import ctypes, math
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
# Shared objects are looked up in ABS_LIB_DIR when it is set, so that CTest
# can run this battery against a CMake build tree without touching the
# repository root.  Unset, it falls back to the root, which is where
# build.sh leaves them.
LIBDIR = Path(os.environ.get("ABS_LIB_DIR", str(ROOT)))
L=ctypes.CDLL(str(LIBDIR / 'libaffine_bundle_solver.so'))
DP=ctypes.POINTER(ctypes.c_double)
L.bsolve_router_meta_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulonglong,ctypes.c_int,DP]
def p(x): return x.ctypes.data_as(DP)

# Exact inconsistent system: x1=0, x2=0, x1+x2=1.
A=np.ascontiguousarray([[1.,0.],[0.,1.],[1.,1.]],dtype=float)
b=np.ascontiguousarray([0.,0.,1.],dtype=float)
xt=np.zeros(2,dtype=float)
o=np.zeros(11,dtype=float)
L.bsolve_router_meta_api(p(A),p(b),p(xt),3,2,1,2,2,777,0,p(o))
assert int(o[0])==3, o
assert math.isfinite(float(o[5])), o       # residual diagnostic remains allowed
assert math.isnan(float(o[6])), o          # no solution witness => no solution error
assert math.isnan(float(o[10])), o         # no deterministic-unique quality certificate
print('PASS incompatible meta API exports no solution-quality field')
