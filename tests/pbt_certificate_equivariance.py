#!/usr/bin/env python3
"""Focused hardening PBT for certificate generation and strict verifier arithmetic.

This battery targets two previously isolated non-hard diagnostics:
  * independent-row-scaling quality of the inconsistent witness generator;
  * strict-verifier availability at extreme binary64 dynamic range.

Oracles are exact constructions and high-precision evaluation of the verifier's
constructive formulas; numpy.linalg.matrix_rank is never used as an oracle.
"""
import argparse, ctypes, json, math, sys
from collections import Counter
from pathlib import Path
import numpy as np
import mpmath as mp

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
import pbt_equivalence_orbits as base

CERT=ctypes.CDLL(str(ROOT/'libcertified_solver.so'))
VER=ctypes.CDLL(str(ROOT/'libstatus_verifier.so'))
DP=ctypes.POINTER(ctypes.c_double)
IP=ctypes.POINTER(ctypes.c_int)

class UniqueWitness(ctypes.Structure):
    _fields_=[('m',ctypes.c_int),('n',ctypes.c_int),('idx',IP),('scale',DP),('perm',IP),('packed_lu',DP),('x',DP)]
class InfiniteWitness(ctypes.Structure):
    _fields_=[('n',ctypes.c_int),('x',DP),('z',DP)]
class InconsistentWitness(ctypes.Structure):
    _fields_=[('m',ctypes.c_int),('y',DP),('pivot_row',ctypes.c_int)]

CERT.bs_generate_unique_witness.argtypes=[DP,DP,ctypes.c_int,ctypes.c_int,ctypes.POINTER(UniqueWitness)]
CERT.bs_generate_unique_witness.restype=ctypes.c_int
CERT.bs_generate_infinite_witness.argtypes=[DP,DP,ctypes.c_int,ctypes.c_int,ctypes.POINTER(InfiniteWitness)]
CERT.bs_generate_infinite_witness.restype=ctypes.c_int
CERT.bs_generate_inconsistent_witness.argtypes=[DP,DP,ctypes.c_int,ctypes.c_int,ctypes.POINTER(InconsistentWitness)]
CERT.bs_generate_inconsistent_witness.restype=ctypes.c_int
VER.bs_unique_witness_free.argtypes=[ctypes.POINTER(UniqueWitness)]
VER.bs_infinite_witness_free.argtypes=[ctypes.POINTER(InfiniteWitness)]
VER.bs_inconsistent_witness_free.argtypes=[ctypes.POINTER(InconsistentWitness)]
VER.bs_verify_unique.argtypes=[DP,DP,ctypes.c_int,ctypes.c_int,ctypes.POINTER(UniqueWitness),DP]
VER.bs_verify_unique.restype=ctypes.c_int
VER.bs_verify_infinite.argtypes=[DP,DP,ctypes.c_int,ctypes.c_int,ctypes.POINTER(InfiniteWitness),DP]
VER.bs_verify_infinite.restype=ctypes.c_int
VER.bs_verify_inconsistent.argtypes=[DP,DP,ctypes.c_int,ctypes.c_int,ctypes.POINTER(InconsistentWitness),DP,DP,DP]
VER.bs_verify_inconsistent.restype=ctypes.c_int

def arr(x): return np.ascontiguousarray(x,dtype=np.float64)
def ptr(x): return x.ctypes.data_as(DP)

class Report:
    def __init__(self): self.counts=Counter(); self.failures=[]; self.stats={}
    def check(self,name,ok,**ctx):
        self.counts[name]+=1
        if not ok and len(self.failures)<300:self.failures.append({'property':name,**ctx})
    def out(self):
        return {'checks':sum(self.counts.values()),'property_counts':dict(self.counts),
                'failures':self.failures,'failure_counts':dict(Counter(f['property'] for f in self.failures)),
                'stats':self.stats}

def generate_verify_inc(A,b):
    A,b=arr(A),arr(b); w=InconsistentWitness(); eta=ctypes.c_double(math.inf);lo=ctypes.c_double();hi=ctypes.c_double()
    grc=CERT.bs_generate_inconsistent_witness(ptr(A),ptr(b),A.shape[0],A.shape[1],ctypes.byref(w))
    if grc: return grc,None,math.inf,math.nan,math.nan,None
    y=np.ctypeslib.as_array(w.y,shape=(A.shape[0],)).copy();k=w.pivot_row
    vrc=VER.bs_verify_inconsistent(ptr(A),ptr(b),A.shape[0],A.shape[1],ctypes.byref(w),ctypes.byref(lo),ctypes.byref(hi),ctypes.byref(eta))
    VER.bs_inconsistent_witness_free(ctypes.byref(w))
    return grc,vrc,eta.value,lo.value,hi.value,(y,k)

def copy_unique(w):
    m,n=w.m,w.n
    return (np.ctypeslib.as_array(w.idx,shape=(n,)).copy(),np.ctypeslib.as_array(w.scale,shape=(n,)).copy(),
            np.ctypeslib.as_array(w.perm,shape=(n,)).copy(),np.ctypeslib.as_array(w.packed_lu,shape=(n*n,)).copy().reshape(n,n),
            np.ctypeslib.as_array(w.x,shape=(n,)).copy())
def copy_infinite(w):
    n=w.n;return np.ctypeslib.as_array(w.x,shape=(n,)).copy(),np.ctypeslib.as_array(w.z,shape=(n,)).copy()
def copy_inconsistent(w):
    m=w.m;return np.ctypeslib.as_array(w.y,shape=(m,)).copy(),w.pivot_row

def mpv(x): return x if isinstance(x, mp.mpf) else mp.mpf(float(x))
def mpnorm(vals): return mp.sqrt(mp.fsum([mpv(v)*mpv(v) for v in vals]))
def shadow_unique(A,b,data):
    idx,scale,perm,LU,x=data;m,n=A.shape;xn=mpnorm(x);best=mp.mpf('0')
    for i in range(m):
        da=mp.mpf('0')
        hits=np.where(idx==i)[0]
        if len(hits):
            ks=int(hits[0]);lr=int(perm[ks]);errs=[]
            for j in range(n):
                s=mp.mpf('0')
                for k in range(n):
                    l=(mpv(LU[lr,k]) if k<lr else (mp.mpf(1) if k==lr else mp.mpf(0)))
                    u=(mpv(LU[k,j]) if k<=j else mp.mpf(0));s+=l*u
                errs.append(mpv(scale[ks])*s-mpv(A[i,j]))
            da=mpnorm(errs)
        res=abs(mp.fsum([mpv(A[i,j])*mpv(x[j]) for j in range(n)])-mpv(b[i]))
        db=res+da*xn;pert=mp.sqrt(da*da+db*db);src=mpnorm(list(A[i])+[b[i]])
        q=(mp.mpf('0') if src==0 and pert==0 else (mp.inf if src==0 else pert/src));best=max(best,q)
    return best

def shadow_infinite(A,b,data):
    x,z=data;m,n=A.shape;zn=mpnorm(z);xn=mpnorm(x);best=mp.mpf('0')
    for i in range(m):
        az=abs(mp.fsum([mpv(A[i,j])*mpv(z[j]) for j in range(n)]));er=az/zn
        res=abs(mp.fsum([mpv(A[i,j])*mpv(x[j]) for j in range(n)])-mpv(b[i]));db=res+er*xn
        pert=mp.sqrt(er*er+db*db);src=mpnorm(list(A[i])+[b[i]])
        q=(mp.mpf('0') if src==0 and pert==0 else (mp.inf if src==0 else pert/src));best=max(best,q)
    return best

def shadow_inconsistent(A,b,data):
    y,k=data;m,n=A.shape
    aty=[mp.fsum([mpv(A[i,j])*mpv(y[i]) for i in range(m)]) for j in range(n)]
    H=mpnorm(aty);er=H/abs(mpv(y[k]));src=mpnorm(list(A[k])+[b[k]])
    return mp.mpf('0') if src==0 and er==0 else (mp.inf if src==0 else er/src)

def run(mode):
    rng=np.random.default_rng(20260813);R=Report();mp.mp.dps=100
    trials=1800 if mode=='full' else 270
    spans=[8,40,100,200,300,500,600,800,1000]
    etas=[]
    # A. Exact inconsistent systems under independent signed dyadic row scalings.
    for t in range(trials):
        n=int(rng.choice([1,2,3,4,6,8,12,16]));m=int(rng.choice([max(1,n//2),n,max(n+1,2*n)]));mr=min(m,n)
        rr=sorted(set([0,mr//2,max(0,mr-1)]));r=int(rng.choice(rr));
        if r>=m:r=max(0,m-1)
        A,b,x=base.family(m,n,r,3,rng,delta=1.0)
        span=spans[t%len(spans)];As,bs=base.row_pow2(A,b,rng,-span,span)
        grc,vrc,eta,lo,hi,_=generate_verify_inc(As,bs);etas.append(eta)
        R.check('inconsistent_row_scaling_generator',grc==0 and vrc==0 and math.isfinite(eta) and eta<1e-10,
                t=t,m=m,n=n,rank=r,span=span,grc=grc,vrc=vrc,eta=eta,ytb=[lo,hi])
    # B. Near-compatible and exactly compatible tall systems: inconsistency radius should remain machine scale.
    near_trials=300 if mode=='full' else 60
    for t in range(near_trials):
        n=int(rng.choice([2,3,4,6,8]));m=2*n;rank=n if t%2==0 else max(1,n-1)
        compatible=(t%3==0); status=(1 if compatible and rank==n else (2 if compatible else 3))
        delta=math.ldexp(1.0,-(10+5*(t%7))) if status==3 else 0.0
        A,b,x=base.family(m,n,rank,status,rng,delta=(delta if status==3 else 1.0))
        As,bs=base.row_pow2(A,b,rng,-500,500)
        # This property belongs to the complete audit profile because an exactly
        # compatible source needs the verifier-mediated normalized tilt.
        c=base.certified(As,bs,x,90000+t);eta=c['eta_inconsistent'];etas.append(eta)
        R.check('tall_zero_distance_inconsistency_availability',math.isfinite(eta) and eta<1e-10,
                t=t,m=m,n=n,rank=rank,status=status,delta=delta,eta=eta,codes=c['codes'],mask=c['mask'])

    # C. Direct strict-verifier global-scale orbits for all three proof types.
    Au=arr([[1.,0.],[0.,1.],[1.,1.],[2.,-1.]])
    xu=arr([0.25,-0.5]);bu=arr(Au@xu)
    wu=UniqueWitness();assert CERT.bs_generate_unique_witness(ptr(Au),ptr(bu),4,2,ctypes.byref(wu))==0
    udata=copy_unique(wu);VER.bs_unique_witness_free(ctypes.byref(wu))
    Ai=arr([[1.,0.,1.],[0.,1.,-1.],[1.,1.,0.],[2.,1.,1.]])
    xi=arr([1.,-2.,0.5]);bi=arr(Ai@xi);wi=InfiniteWitness();assert CERT.bs_generate_infinite_witness(ptr(Ai),ptr(bi),4,3,ctypes.byref(wi))==0
    idata=copy_infinite(wi);VER.bs_infinite_witness_free(ctypes.byref(wi))
    Ac=arr([[1.,-2.],[2.,-4.],[-1.,2.],[3.,-6.]])
    bc=arr([1.,2.,-1.,4.]);wc=InconsistentWitness();assert CERT.bs_generate_inconsistent_witness(ptr(Ac),ptr(bc),4,2,ctypes.byref(wc))==0
    cdata=copy_inconsistent(wc);VER.bs_inconsistent_witness_free(ctypes.byref(wc))
    exps=[-1070,-1060,-1040,-1022,-1000,-800,-600,-400,-200,0,200,400,600,800,1000,1010,1020]
    if mode=='quick':exps=[-1070,-1040,-1000,-600,0,600,1000,1020]
    for e in exps:
        s=math.ldexp(1.0,e)
        # Unique: normalized selected block is unchanged under positive global scaling.
        Ag=arr(np.ldexp(Au,e));bg=arr(np.ldexp(bu,e));idx,sc,perm,LU,xx=udata
        idxc=np.ascontiguousarray(idx,dtype=np.int32);scc=arr(np.ldexp(sc,e));permc=np.ascontiguousarray(perm,dtype=np.int32);LUc=arr(LU.ravel());xxc=arr(xx)
        w=UniqueWitness(4,2,idxc.ctypes.data_as(IP),ptr(scc),permc.ctypes.data_as(IP),ptr(LUc),ptr(xxc));eta=ctypes.c_double(math.inf)
        rc=VER.bs_verify_unique(ptr(Ag),ptr(bg),4,2,ctypes.byref(w),ctypes.byref(eta))
        if e>=-1022:
            R.check('strict_unique_extreme_global_scale',rc==0 and math.isfinite(eta.value) and eta.value<1e-10,e=e,rc=rc,eta=eta.value)
        else:
            R.check('strict_unique_subnormal_availability',rc==0 and math.isfinite(eta.value) and eta.value<1.0,e=e,rc=rc,eta=eta.value)
        # Infinite witness is invariant under global positive scaling.
        Ag=arr(np.ldexp(Ai,e));bg=arr(np.ldexp(bi,e));xx,zz=idata;xx=arr(xx);zz=arr(zz);w2=InfiniteWitness(3,ptr(xx),ptr(zz));eta2=ctypes.c_double(math.inf)
        rc2=VER.bs_verify_infinite(ptr(Ag),ptr(bg),4,3,ctypes.byref(w2),ctypes.byref(eta2))
        if e>=-1022:
            R.check('strict_infinite_extreme_global_scale',rc2==0 and math.isfinite(eta2.value) and eta2.value<1e-10,e=e,rc=rc2,eta=eta2.value)
        else:
            R.check('strict_infinite_subnormal_availability',rc2==0 and math.isfinite(eta2.value) and eta2.value<1.0,e=e,rc=rc2,eta=eta2.value)
        # Inconsistent proof is homogeneous in y; the strict checker evaluates products in a common exponent frame.
        Ag=arr(np.ldexp(Ac,e));bg=arr(np.ldexp(bc,e));yy,k=cdata;yy=arr(yy);w3=InconsistentWitness(4,ptr(yy),k);lo=ctypes.c_double();hi=ctypes.c_double();eta3=ctypes.c_double(math.inf)
        rc3=VER.bs_verify_inconsistent(ptr(Ag),ptr(bg),4,2,ctypes.byref(w3),ctypes.byref(lo),ctypes.byref(hi),ctypes.byref(eta3))
        if e>=-1022:
            R.check('strict_inconsistent_extreme_global_scale',rc3==0 and math.isfinite(eta3.value) and eta3.value<1e-10,e=e,rc=rc3,eta=eta3.value,ytb=[lo.value,hi.value])
        else:
            R.check('strict_inconsistent_subnormal_availability',rc3==0 and math.isfinite(eta3.value) and eta3.value<1.0,e=e,rc=rc3,eta=eta3.value,ytb=[lo.value,hi.value])

    # D. High-precision shadow check of accepted radius: strict eta must not be below the exact constructive formula.
    shadow_trials=120 if mode=='full' else 24
    shadow_ratios=[]
    for t in range(shadow_trials):
        typ=t%3;e=int(rng.choice([-1000,-600,-200,0,200,600,1000]))
        if typ==0:
            A=arr(np.ldexp(Au,e));b=arr(np.ldexp(bu,e));idx,sc,perm,LU,xx=udata
            idxc=np.ascontiguousarray(idx,dtype=np.int32);scc=arr(np.ldexp(sc,e));permc=np.ascontiguousarray(perm,dtype=np.int32);LUc=arr(LU.ravel());xxc=arr(xx)
            w=UniqueWitness(4,2,idxc.ctypes.data_as(IP),ptr(scc),permc.ctypes.data_as(IP),ptr(LUc),ptr(xxc));eta=ctypes.c_double(math.inf)
            rc=VER.bs_verify_unique(ptr(A),ptr(b),4,2,ctypes.byref(w),ctypes.byref(eta));q=shadow_unique(A,b,(idx, np.ldexp(sc,e), perm, LU, xx))
        elif typ==1:
            A=arr(np.ldexp(Ai,e));b=arr(np.ldexp(bi,e));xx,zz=idata;xx=arr(xx);zz=arr(zz);w=InfiniteWitness(3,ptr(xx),ptr(zz));eta=ctypes.c_double(math.inf)
            rc=VER.bs_verify_infinite(ptr(A),ptr(b),4,3,ctypes.byref(w),ctypes.byref(eta));q=shadow_infinite(A,b,idata)
        else:
            A=arr(np.ldexp(Ac,e));b=arr(np.ldexp(bc,e));yy,k=cdata;yy=arr(yy);w=InconsistentWitness(4,ptr(yy),k);lo=ctypes.c_double();hi=ctypes.c_double();eta=ctypes.c_double(math.inf)
            rc=VER.bs_verify_inconsistent(ptr(A),ptr(b),4,2,ctypes.byref(w),ctypes.byref(lo),ctypes.byref(hi),ctypes.byref(eta));q=shadow_inconsistent(A,b,cdata)
        ok=rc==0 and mp.mpf(eta.value)>=q
        if q>0 and math.isfinite(eta.value):shadow_ratios.append(float(mp.mpf(eta.value)/q))
        R.check('high_precision_outward_radius',ok,t=t,type=typ,e=e,rc=rc,eta=eta.value,shadow=str(q))
    finite=[v for v in etas if math.isfinite(v)]
    R.stats['inconsistent_eta_max']=max(finite) if finite else math.inf
    R.stats['inconsistent_eta_median']=float(np.median(finite)) if finite else math.inf
    R.stats['shadow_ratio_min']=min(shadow_ratios) if shadow_ratios else math.nan
    R.stats['shadow_ratio_max']=max(shadow_ratios) if shadow_ratios else math.nan
    return R

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['quick','full'],default='full');ap.add_argument('--output',default=str(ROOT/'results/pbt_certificate_hardening.json'));ap.add_argument('--strict',action='store_true');args=ap.parse_args()
    R=run(args.mode);out=R.out();Path(args.output).write_text(json.dumps(out,indent=2,allow_nan=True)+'\n')
    print(json.dumps({k:out[k] for k in ('checks','failure_counts','stats')},indent=2))
    return 1 if args.strict and out['failures'] else 0
if __name__=='__main__':raise SystemExit(main())
