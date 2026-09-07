#!/usr/bin/env python3
"""Controlled affine-translation threshold for the fast contradiction policy.

The exact equality problem is invariant under x=y+c, b'=b-Ac.  For a normalized
row (a_hat,beta) and affine-related anchor x, the exact compatibility residual
rho=beta-a_hat^T x is unchanged, whereas the implementation's source-row
contradiction threshold tc*(1+|beta|+||x||) grows with the coordinate offset.
This script demonstrates the resulting policy threshold on a 3x2 exact-
inconsistent system and records the analytic sufficient-preservation/failure
bounds along a dyadic translation ray.
"""
import ctypes, json, math
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
L=ctypes.CDLL(str(ROOT/'libaffine_bundle_solver.so'))
DP=ctypes.POINTER(ctypes.c_double)
L.bsolve_router_meta_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulonglong,ctypes.c_int,DP]
def p(x): return x.ctypes.data_as(DP)
def router(A,b,x,seed=777):
    A=np.ascontiguousarray(A,float);b=np.ascontiguousarray(b,float);x=np.ascontiguousarray(x,float);o=np.zeros(11)
    L.bsolve_router_meta_api(p(A),p(b),p(x),A.shape[0],A.shape[1],1,2,2,seed,0,p(o))
    return {'status':int(o[0]),'certainty':int(o[1]),'rank':int(o[2]),'lo':int(o[3]),'hi':int(o[4]),
            'relres':None if not np.isfinite(o[5]) else float(o[5])}

# First two rows set x=0; the third is dependent but has a fixed contradiction.
A=np.array([[1.,0.],[0.,1.],[1.,1.]],dtype=float)
b=np.array([0.,0.,1.],dtype=float)
x=np.zeros(2)
c0=np.array([1.,1.])
tc=2e-10
ahat=A[2]/np.linalg.norm(A[2]); beta=b[2]/np.linalg.norm(A[2])
rho=beta-ahat@x
K=abs(ahat@c0)+np.linalg.norm(c0)
B0=1+abs(beta)+np.linalg.norm(x)
# If 2^e K < |rho|/tc-B0, contradiction is guaranteed to survive the policy gate.
# If 2^e K >= |rho|/tc-1+|beta|+||x||, the gate is guaranteed not to fire.
preserve_numerator=abs(rho)/tc - B0
fail_numerator=abs(rho)/tc - 1 + abs(beta)+np.linalg.norm(x)
preserve_rhs=preserve_numerator/K
fail_rhs=fail_numerator/K
preserve_e=math.log2(preserve_rhs)
fail_e=math.log2(fail_rhs)
rows=[]
for e in range(24,35):
    c=np.ldexp(c0,e); bt=b-A@c; xt=x-c
    rows.append({'exp':e,'scale':float(2.0**e),'router':router(A,bt,xt)})
out={'tc':tc,'rho':float(rho),'K':float(K),'B0':float(B0),
     'sufficient_preservation_scale_formula':'(|rho|/tc - B0)/K',
     'guaranteed_gate_failure_scale_formula':'(|rho|/tc - 1 + |beta| + ||x||_2)/K',
     'sufficient_preservation_numerator':float(preserve_numerator),
     'guaranteed_gate_failure_numerator':float(fail_numerator),
     'sufficient_preservation_log2_bound':preserve_e,
     'guaranteed_gate_failure_log2_bound':fail_e,
     'rows':rows}
path=ROOT/'results/affine_translation_policy_gate.json'; path.write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
