#!/usr/bin/env python3
"""Property/metamorphic test battery for the C affine-bundle solver.

No external PBT framework is required.  The generators construct exact binary64
integer/dyadic systems with known algebraic rank/status, then traverse orbits of
transformations that preserve the equality problem or change it predictably.

Default mode writes a JSON report and returns success even when scientific
counterexamples are found.  Use --strict to make hard property violations exit 1.
"""
import argparse, ctypes, json, math, os
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FAST = ctypes.CDLL(str(ROOT / 'libaffine_bundle_solver.so'))
CERT = ctypes.CDLL(str(ROOT / 'libcertified_solver.so'))
DP = ctypes.POINTER(ctypes.c_double)

class Certified(ctypes.Structure):
    _fields_=[('fast_status',ctypes.c_int),('fast_certainty',ctypes.c_int),
              ('rank_estimate',ctypes.c_int),('rank_lo',ctypes.c_int),('rank_hi',ctypes.c_int),
              ('eta_x',ctypes.c_double),('certified_status',ctypes.c_int),
              ('eta_status',ctypes.c_double),('generator_code',ctypes.c_int),('verifier_code',ctypes.c_int),
              ('accepted_status_mask',ctypes.c_int),
              ('eta_unique',ctypes.c_double),('eta_infinite',ctypes.c_double),('eta_inconsistent',ctypes.c_double),
              ('unique_generator_code',ctypes.c_int),('unique_verifier_code',ctypes.c_int),
              ('infinite_generator_code',ctypes.c_int),('infinite_verifier_code',ctypes.c_int),
              ('inconsistent_generator_code',ctypes.c_int),('inconsistent_verifier_code',ctypes.c_int)]

FAST.bsolve_router_meta_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,
    ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulonglong,ctypes.c_int,DP]
FAST.bsolve_seq_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,DP]
CERT.bsolve_certified_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,
    ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulonglong,ctypes.c_int,
    ctypes.POINTER(Certified)]

def arr(x): return np.ascontiguousarray(x,dtype=np.float64)
def ptr(x): return x.ctypes.data_as(DP)

def router(A,b,x,seed=1,sp=1,qv=2,alpha=2,full=0):
    A,b,x=arr(A),arr(b),arr(x); out=np.zeros(11,dtype=np.float64)
    FAST.bsolve_router_meta_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],sp,qv,alpha,
                                seed,full,ptr(out))
    return {'status':int(out[0]),'certainty':int(out[1]),'rank':int(out[2]),
            'lo':int(out[3]),'hi':int(out[4]),'relres':float(out[5]),
            'relx':float(out[6]),'eta_x':float(out[10])}

def seq(A,b,x):
    A,b,x=arr(A),arr(b),arr(x); out=np.zeros(7,dtype=np.float64)
    FAST.bsolve_seq_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],ptr(out))
    return {'status':int(out[0]),'rank':int(out[1]),'relres':float(out[5]),'relx':float(out[6])}

def certified(A,b,x,seed=1):
    A,b,x=arr(A),arr(b),arr(x); o=Certified()
    rc=CERT.bsolve_certified_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],1,2,2,
                                 seed,0,ctypes.byref(o))
    if rc: raise RuntimeError(f'certified api rc={rc}')
    return {'status':o.fast_status,'certainty':o.fast_certainty,'rank':o.rank_estimate,
            'lo':o.rank_lo,'hi':o.rank_hi,'mask':o.accepted_status_mask,
            'eta_unique':o.eta_unique,'eta_infinite':o.eta_infinite,
            'eta_inconsistent':o.eta_inconsistent,'eta_x':o.eta_x,
            'codes':[o.unique_generator_code,o.unique_verifier_code,
                     o.infinite_generator_code,o.infinite_verifier_code,
                     o.inconsistent_generator_code,o.inconsistent_verifier_code]}

# Exact constructors.  U=[I;C], V=[I D] gives rank(A)=r exactly over R.
def family(m,n,r,status,rng,delta=1.0):
    assert 0 <= r <= min(m,n)
    if status==1: assert m>=n and r==n
    if status==2: assert r<n
    if status==3: assert r<m
    if r:
        C=rng.integers(-3,4,size=(m-r,r),dtype=np.int64)
        U=np.vstack([np.eye(r,dtype=np.int64),C])
        D=rng.integers(-3,4,size=(r,n-r),dtype=np.int64)
        V=np.hstack([np.eye(r,dtype=np.int64),D])
        A=(U@V).astype(np.float64)
    else:
        C=np.zeros((m,0),dtype=np.int64); A=np.zeros((m,n),dtype=np.float64)
    x=rng.integers(-3,4,size=n).astype(np.float64)
    b=A@x
    if status==3:
        if r==0:
            y=np.zeros(m); y[0]=1.0
        else:
            t=np.zeros(m-r,dtype=np.int64); t[0]=1
            y=np.concatenate([-(C.T@t),t]).astype(np.float64) # y^T A = 0 exactly
        b=b+delta*y
    return arr(A),arr(b),arr(x)

def normalized_rank_separation(A,r):
    if r==0: return math.inf
    rn=np.linalg.norm(A,axis=1); B=A[rn>0]/rn[rn>0,None]
    s=np.linalg.svd(B,compute_uv=False)
    return float(s[r-1]/s[0]) if len(s)>=r and s[0]>0 else 0.0

def row_perm(A,b,rng):
    p=rng.permutation(A.shape[0]); return arr(A[p]),arr(b[p])
def row_pow2(A,b,rng,klo=-12,khi=12):
    k=rng.integers(klo,khi+1,size=A.shape[0]); sign=np.where(rng.integers(0,2,size=A.shape[0]),1.0,-1.0)
    s=np.ldexp(sign,k); return arr(A*s[:,None]),arr(b*s)
def global_pow2(A,b,k):
    s=math.ldexp(1.0,k); return arr(A*s),arr(b*s)
def append_duplicates(A,b,rng,k=2):
    ix=rng.integers(0,A.shape[0],size=k); return arr(np.vstack([A,A[ix]])),arr(np.r_[b,b[ix]])
def append_combinations(A,b,rng,k=2):
    c=rng.integers(-2,3,size=(k,A.shape[0]),dtype=np.int64)
    return arr(np.vstack([A,c@A])),arr(np.r_[b,c@b])
def left_unimodular(A,b,rng,steps=6):
    A=A.copy();b=b.copy();m=A.shape[0]
    for _ in range(steps):
        if m<2: break
        i,j=rng.choice(m,2,replace=False);q=int(rng.choice([-2,-1,1,2]));A[i]+=q*A[j];b[i]+=q*b[j]
        if rng.random()<0.2: A[[i,j]]=A[[j,i]];b[[i,j]]=b[[j,i]]
    return arr(A),arr(b)
def signed_col_perm(A,x,rng):
    n=A.shape[1];p=rng.permutation(n);s=np.where(rng.integers(0,2,size=n),1.0,-1.0)
    return arr(A[:,p]*s),arr(s*x[p])
def right_unimodular(A,x,rng,steps=5):
    n=A.shape[1];T=np.eye(n,dtype=np.int64);ops=[]
    for _ in range(steps):
        if n<2: break
        i,j=rng.choice(n,2,replace=False);q=int(rng.choice([-2,-1,1,2]));T[:,i]+=q*T[:,j];ops.append((i,j,q))
    Ap=arr(A@T.astype(np.float64));xp=x.copy()
    for i,j,q in reversed(ops): xp[j]-=q*xp[i]
    return Ap,arr(xp)
def hadamard(n):
    H=np.array([[1.0]])
    while H.shape[0]<n: H=np.block([[H,H],[H,-H]])
    return H/math.sqrt(n)
def hadamard_cols(A,x):
    H=hadamard(A.shape[1]);return arr(A@H),arr(H.T@x)
def affine_shift(A,b,x,rng,exp=0):
    c=rng.integers(-3,4,size=A.shape[1]).astype(np.float64);c=np.ldexp(c,exp)
    return A,arr(b-A@c),arr(x-c)
def direct_sum(A1,b1,x1,A2,b2,x2):
    m1,n1=A1.shape;m2,n2=A2.shape;A=np.zeros((m1+m2,n1+n2));A[:m1,:n1]=A1;A[m1:,n1:]=A2
    return arr(A),arr(np.r_[b1,b2]),arr(np.r_[x1,x2])

class Report:
    def __init__(self): self.counts=Counter();self.failures=[];self.notes=[]
    def check(self,prop,ok,severity='hard',**ctx):
        self.counts[prop]+=1
        if not ok:
            item={'property':prop,'severity':severity,**ctx};self.failures.append(item)
    def compact(self):
        sev=Counter(f['severity'] for f in self.failures); props=Counter(f['property'] for f in self.failures)
        return {'checks':sum(self.counts.values()),'property_counts':dict(self.counts),
                'failure_counts_by_severity':dict(sev),'failure_counts_by_property':dict(props),
                'failures':self.failures[:200],'notes':self.notes}

def exact_status_ok(q,status,rank):
    if q['status']!=status: return False
    return status==3 or q['rank']==rank or (q['lo']<=rank<=q['hi'])

def run(mode='full'):
    rng=np.random.default_rng(20260812);R=Report()
    trials=180 if mode=='full' else 45
    dims=[1,2,3,4,8,16,31,47,48,49,64,96]
    # 1) Exact oracle + rank interval + equivalence orbits.
    for t in range(trials):
        n=dims[t%len(dims)]
        ratio=[0.5,1.0,2.0,4.0][(t//len(dims))%4]
        m=max(1,int(round(n*ratio)))
        mr=min(m,n)
        ranks=sorted(set([0,min(1,mr),mr//2,max(0,mr-1),mr]))
        candidates=[]
        if m>=n: candidates.append((1,n))
        for r in ranks:
            if r<n: candidates.append((2,r))
            if r<m: candidates.append((3,r))
        status,rank=candidates[int(rng.integers(len(candidates)))]
        A,b,x=family(m,n,rank,status,rng,delta=2.0)
        sep=normalized_rank_separation(A,rank)
        base=router(A,b,x,1000+t)
        well=(rank==0 or sep>1e-5)
        R.check('exact_base_status', exact_status_ok(base,status,rank), 'hard',t=t,m=m,n=n,status=status,rank=rank,sep=sep,got=base)
        if well and status!=3:
            R.check('rank_interval_contains_exact_well_separated',base['lo']<=rank<=base['hi'],'hard',t=t,m=m,n=n,status=status,rank=rank,sep=sep,got=base)
        transforms=[]
        Ap,bp=row_perm(A,b,rng);transforms.append(('row_permutation',Ap,bp,x))
        As,bs=row_pow2(A,b,rng);transforms.append(('signed_dyadic_row_scaling',As,bs,x))
        Ad,bd=append_duplicates(A,b,rng);transforms.append(('duplicate_equations',Ad,bd,x))
        Ac,bc=append_combinations(A,b,rng);transforms.append(('dependent_equation_extension',Ac,bc,x))
        Al,bl=left_unimodular(A,b,rng);transforms.append(('unimodular_row_mixing',Al,bl,x))
        Apc,xpc=signed_col_perm(A,x,rng);transforms.append(('signed_column_permutation',Apc,b,xpc))
        Au,xu=right_unimodular(A,x,rng);transforms.append(('unimodular_coordinate_change',Au,b,xu))
        transforms.append(('rhs_sign',A,-b,-x)); transforms.append(('coefficient_sign',-A,b,-x))
        if n in (1,2,4,8,16,32,64):
            Ah,xh=hadamard_cols(A,x);transforms.append(('hadamard_orthogonal_coordinates',Ah,b,xh))
        for name,At,bt,xt in transforms:
            q=router(At,bt,xt,1000+t)
            R.check(name, exact_status_ok(q,status,rank),'hard',t=t,m=m,n=n,status=status,rank=rank,sep=sep,got=q)
            if well and status!=3:
                R.check(name+'_rank_interval',q['lo']<=rank<=q['hi'],'hard',t=t,m=m,n=n,status=status,rank=rank,sep=sep,got=q)
        # Moderate affine translations: exact-equivalence stress, but representation metric is not invariant.
        for e in (0,10,20,30):
            At,bt,xt=affine_shift(A,b,x,rng,e);q=router(At,bt,xt,1000+t)
            sev='known-representation' if e>=20 else 'hard'
            R.check(f'affine_translation_2^{e}', exact_status_ok(q,status,rank),sev,t=t,m=m,n=n,status=status,rank=rank,got=q)

    # 2) Predictable structural metamorphisms.
    structural=120 if mode=='full' else 30
    shapes=[(1,3),(2,4),(4,2),(4,4),(8,4),(4,8),(12,6),(6,12)]
    for t in range(structural):
        m,n=shapes[t%len(shapes)]; mr=min(m,n)
        if m>=n and t%2==0: status,rank=1,n
        else: status,rank=2,max(0,mr-1)
        A,b,x=family(m,n,rank,status,rng)
        Az=np.vstack([A,np.zeros((1,n))]);bz=np.r_[b,0.0];q=router(Az,bz,x,3000+t)
        R.check('append_zero_equation',exact_status_ok(q,status,rank),'hard',t=t,m=m,n=n,status=status,rank=rank,got=q)
        q=router(Az,np.r_[b,1.0],x,3000+t)
        R.check('append_zero_contradiction',q['status']==3,'hard',t=t,m=m,n=n,got=q)
        Acol=np.hstack([A,np.zeros((m,1))]);xcol=np.r_[x,0.0];q=router(Acol,b,xcol,3000+t)
        R.check('append_free_variable',q['status']==2 and q['lo']<=rank<=q['hi'],'hard',t=t,m=m,n=n,rank=rank,got=q)

    # 3) Direct-sum algebra U⊕U=U, U⊕I=I, I⊕I=I, X dominates.
    for t in range(80 if mode=='full' else 20):
        s1,s2=[(1,1),(1,2),(2,2),(1,3),(2,3),(3,3)][t%6]
        def mk(s,m,n):
            if s==1:return family(m,n,n,1,rng)
            r=max(0,min(m,n)-1);return family(m,n,r,s,rng)
        A1,b1,x1=mk(s1,4,3);A2,b2,x2=mk(s2,5,3);A,b,x=direct_sum(A1,b1,x1,A2,b2,x2)
        expected=3 if 3 in (s1,s2) else (2 if 2 in (s1,s2) else 1);q=router(A,b,x,4000+t)
        R.check('direct_sum_status_algebra',q['status']==expected,'hard',t=t,s1=s1,s2=s2,expected=expected,got=q)

    # 4) Algorithm-configuration orbit: seed/sketch density/validation count/core size/full residual.
    cfg_trials=80 if mode=='full' else 20
    cfgs=[(1,1,1,0),(1,2,2,0),(2,2,2,0),(4,2,2,0),(1,4,4,0),(1,2,2,1)]
    for t in range(cfg_trials):
        n=int(rng.choice([2,4,8,16,31,47,48,49,64]));m=max(2,int(rng.choice([max(2,n//2),n,2*n])))
        mr=min(m,n);r=int(rng.choice(sorted(set([0,min(1,mr),mr//2,max(0,mr-1)]))))
        status=2 if r<n else 1
        A,b,x=family(m,n,r,status,rng)
        sep=normalized_rank_separation(A,r); well=(r==0 or sep>1e-5)
        for ci,(sp,qv,alpha,full) in enumerate(cfgs):
            q=router(A,b,x,8000+t*17+ci,sp=sp,qv=qv,alpha=alpha,full=full)
            R.check('configuration_orbit_status',exact_status_ok(q,status,r),'hard',t=t,m=m,n=n,rank=r,sep=sep,config=[sp,qv,alpha,full],got=q)
            if well:R.check('configuration_orbit_rank_interval',q['lo']<=r<=q['hi'],'hard',t=t,m=m,n=n,rank=r,sep=sep,config=[sp,qv,alpha,full],got=q)

    # 5) Source-status certificate completeness + metric-isometry stress.
    cert_trials=600 if mode=='full' else 120
    for t in range(cert_trials):
        n=int(rng.choice([1,2,3,4,6,8,12,16]));m=int(rng.choice([max(1,n//2),n,max(n+1,2*n)]));mr=min(m,n)
        opts=[]
        if m>=n:opts.append((1,n))
        for r in sorted(set([0,mr//2,max(0,mr-1)])):
            if r<n:opts.append((2,r))
            if r<m:opts.append((3,r))
        status,rank=opts[int(rng.integers(len(opts)))];A,b,x=family(m,n,rank,status,rng,delta=1.0)
        c0=certified(A,b,x,5000+t);key={1:'eta_unique',2:'eta_infinite',3:'eta_inconsistent'}[status];v=c0[key]
        R.check('source_status_certificate_machine_scale',math.isfinite(v) and v<1e-10,'generator-quality',t=t,m=m,n=n,status=status,rank=rank,value=v,got=c0)
        # Exact metric isometries: row permutation, signed row scale, global dyadic scale, signed column permutation.
        cases=[];Ap,bp=row_perm(A,b,rng);cases.append(('profile_row_permutation',Ap,bp,x));As,bs=row_pow2(A,b,rng,-8,8);cases.append(('profile_row_scaling',As,bs,x));Acp,xcp=signed_col_perm(A,x,rng);cases.append(('profile_signed_column_permutation',Acp,b,xcp));Ag,bg=global_pow2(A,b,int(rng.integers(-20,21)));cases.append(('profile_global_scaling',Ag,bg,x))
        for name,At,bt,xt in cases:
            c1=certified(At,bt,xt,5000+t);vv=c1[key]
            R.check(name,math.isfinite(vv) and vv<1e-10,'generator-quality',t=t,m=m,n=n,status=status,rank=rank,value=vv,got=c1)

    # 6) Dynamic-range isometry of the verifier on a fixed exact-unique system.
    A=np.array([[1.,0.],[0.,1.],[1.,1.],[2.,-1.]]);x=np.array([2.,-3.]);b=A@x
    for e in (-1000,-800,-600,-500,-400,-200,0,200,400,500,600,800,1000):
        Ag,bg=global_pow2(A,b,e);c=certified(Ag,bg,x,777);ok=math.isfinite(c['eta_unique']) and c['eta_unique']<1e-10
        R.check('certificate_extreme_global_scaling',ok,'range-robustness',exp=e,value=c['eta_unique'],mask=c['mask'],codes=c['codes'])

    # 7) Exact-inconsistent coordinate translation sweep (known representation sensitivity).
    for t in range(40 if mode=='full' else 10):
        A,b,x=family(12,4,3,3,rng,delta=1.0)
        for e in (0,10,20,30,40,50,60):
            At,bt,xt=affine_shift(A,b,x,rng,e);q=router(At,bt,xt,7000+t)
            R.check('inconsistent_affine_translation_sweep',q['status']==3,'known-representation',t=t,exp=e,got=q)

    # 8) Fixed minimal shrunk counterexample: source direct scan vs router vs trusted audit.
    A=np.array([[-8.,20.],[6.,-15.],[-10.,25.],[-6.,15.]])
    x=np.array([-1.,-2.]);b=A@x
    q=router(A,b,x,11);s=seq(A,b,x);c=certified(A,b,x,11)
    R.check('minimal_rank1_counterexample',q['status']==2 and q['lo']<=1<=q['hi'],'hard',A=A.tolist(),b=b.tolist(),x=x.tolist(),router=q,seq=s,certified=c)
    R.notes.append({'minimal_counterexample':{'A':A.tolist(),'b':b.tolist(),'exact_rank':1,'exact_status':'infinite','router':q,'sequential_source_scan':s,'certified_audit':c}})
    return R

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['quick','full'],default='full');ap.add_argument('--strict',action='store_true');ap.add_argument('--output',default=str(ROOT/'results/pbt_equivalence_report.json'));args=ap.parse_args()
    R=run(args.mode);report=R.compact();Path(args.output).write_text(json.dumps(report,indent=2,allow_nan=True)+'\n')
    print(json.dumps({k:report[k] for k in ['checks','failure_counts_by_severity','failure_counts_by_property']},indent=2))
    hard=report['failure_counts_by_severity'].get('hard',0)
    if args.strict and hard:return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
