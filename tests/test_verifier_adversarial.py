import ctypes
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
lib = ctypes.CDLL(str(ROOT/'libstatus_verifier.so'))
DP = ctypes.POINTER(ctypes.c_double)
IP = ctypes.POINTER(ctypes.c_int)

class UniqueWitness(ctypes.Structure):
    _fields_ = [('m',ctypes.c_int),('n',ctypes.c_int),('idx',IP),('scale',DP),
                ('perm',IP),('packed_lu',DP),('x',DP)]
class InfiniteWitness(ctypes.Structure):
    _fields_ = [('n',ctypes.c_int),('x',DP),('z',DP)]
class InconsistentWitness(ctypes.Structure):
    _fields_ = [('m',ctypes.c_int),('y',DP),('pivot_row',ctypes.c_int)]

lib.bs_verify_unique.argtypes=[DP,DP,ctypes.c_int,ctypes.c_int,ctypes.POINTER(UniqueWitness),DP]
lib.bs_verify_infinite.argtypes=[DP,DP,ctypes.c_int,ctypes.c_int,ctypes.POINTER(InfiniteWitness),DP]
lib.bs_verify_inconsistent.argtypes=[DP,DP,ctypes.c_int,ctypes.c_int,ctypes.POINTER(InconsistentWitness),DP,DP,DP]

def dptr(a): return np.ascontiguousarray(a,dtype=np.float64).ctypes.data_as(DP)
def iptr(a): return np.ascontiguousarray(a,dtype=np.int32).ctypes.data_as(IP)

# A non-bijective row map must never be accepted as a permutation witness.
A=np.eye(2,dtype=np.float64); b=np.zeros(2); x=np.zeros(2)
idx=np.array([0,1],dtype=np.int32); scale=np.ones(2); perm=np.array([0,0],dtype=np.int32); lu=np.eye(2)
w=UniqueWitness(2,2,iptr(idx),dptr(scale),iptr(perm),dptr(lu),dptr(x)); eta=np.array([0.0])
assert lib.bs_verify_unique(dptr(A),dptr(b),2,2,ctypes.byref(w),dptr(eta)) != 0

# The infinite-status object needs a genuine nonzero null direction.
z=np.zeros(2); wi=InfiniteWitness(2,dptr(x),dptr(z)); eta[:]=0
assert lib.bs_verify_infinite(dptr(A),dptr(b),2,2,ctypes.byref(wi),dptr(eta)) != 0

# A left-null candidate whose y^T b interval contains zero cannot prove inconsistency.
Az=np.zeros((2,1)); bz=np.array([1.0,1.0]); y=np.array([1.0,-1.0]);
wc=InconsistentWitness(2,dptr(y),0); lo=np.array([0.0]); hi=np.array([0.0]); eta[:]=0
assert lib.bs_verify_inconsistent(dptr(Az),dptr(bz),2,1,ctypes.byref(wc),dptr(lo),dptr(hi),dptr(eta)) != 0

print('adversarial verifier checks: PASS')
