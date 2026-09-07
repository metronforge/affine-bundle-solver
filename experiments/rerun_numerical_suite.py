#!/usr/bin/env python3
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','4')
import argparse, ctypes, json, math, platform, subprocess, time
from pathlib import Path
import numpy as np
from scipy.linalg import hadamard
from threadpoolctl import threadpool_limits, threadpool_info

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'libaffine_bundle_solver.so'
DP=ctypes.POINTER(ctypes.c_double)
STATUS={1:'unique',2:'infinite',3:'inconsistent',4:'undecidable'}
CLS={1:'unique',2:'infinite',3:'inconsistent',4:'fail',5:'undecidable'}

def ptr(a): return a.ctypes.data_as(DP)

def load():
    L=ctypes.CDLL(str(LIB))
    L.bsolve_router_meta_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulonglong,ctypes.c_int,DP]
    L.bsolve_seq_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,DP]
    L.bsolve_lapack_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,DP]
    L.bsolve_fg_counters_reset_api.argtypes=[]
    L.bsolve_fg_counters_api.argtypes=[ctypes.POINTER(ctypes.c_ulonglong)]
    return L

LIBGOMP=None
try:
    LIBGOMP=ctypes.CDLL('libgomp.so.1')
    LIBGOMP.omp_set_num_threads.argtypes=[ctypes.c_int]
except OSError:
    pass

def omp_threads(k):
    if LIBGOMP is not None: LIBGOMP.omp_set_num_threads(int(k))

def router(L,A,b,x,seed=777,omp=4):
    omp_threads(omp)
    out=np.zeros(11,np.float64)
    L.bsolve_router_meta_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],1,2,2,int(seed),0,ptr(out))
    return out

def seq(L,A,b,x):
    omp_threads(1)
    out=np.zeros(7,np.float64)
    L.bsolve_seq_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],ptr(out))
    return out

def med_router(L,A,b,x,omp=4,warm=4,reps=11,seed=777):
    for q in range(warm): router(L,A,b,x,seed+q,omp)
    vals=[]; last=None
    for q in range(reps):
        last=router(L,A,b,x,seed+100+q,omp); vals.append(float(last[7]))
    return float(np.median(vals)),last,vals

def med_seq(L,A,b,x,warm=2,reps=7):
    for _ in range(warm): seq(L,A,b,x)
    vals=[];last=None
    for _ in range(reps):
        last=seq(L,A,b,x);vals.append(float(last[4]))
    return float(np.median(vals)),last,vals

def H(n): return np.ascontiguousarray(hadamard(n,dtype=np.float64)/math.sqrt(n))

def make_random(m,n,r,seed=1):
    rng=np.random.default_rng(seed); hh=H(n)[:r]
    C=rng.standard_normal((m,r))
    A=np.ascontiguousarray(C@hh,dtype=np.float64)
    x=np.ascontiguousarray(rng.standard_normal(n),dtype=np.float64)
    b=np.ascontiguousarray(A@x,dtype=np.float64)
    return A,b,x

def make_grouped(m,n,rank=None,seed=2,inconsistent=False):
    if rank is None: rank=n
    rng=np.random.default_rng(seed); hh=H(n)
    idx=(np.arange(m)*rank//m).clip(max=rank-1)
    A=np.ascontiguousarray(hh[idx],dtype=np.float64)
    x=np.ascontiguousarray(rng.standard_normal(n),dtype=np.float64)
    b=np.ascontiguousarray(A@x,dtype=np.float64)
    if inconsistent: b[-1]+=0.25
    return A,b,x


def make_integer_rank(m,n,r,seed=11):
    rng=np.random.default_rng(seed)
    U=rng.integers(-3,4,size=(m,r),dtype=np.int64).astype(np.float64)
    U[:r,:]=np.eye(r)
    V=rng.integers(-3,4,size=(r,n),dtype=np.int64).astype(np.float64)
    V[:,:r]=np.eye(r)
    A=np.ascontiguousarray(U@V)
    x=np.ascontiguousarray(rng.integers(-3,4,size=n).astype(np.float64))
    b=np.ascontiguousarray(A@x)
    return A,b,x

def make_digits(seed=3):
    from sklearn.datasets import load_digits
    X=load_digits().data.astype(np.float64)
    keep=np.ptp(X,axis=0)>0
    A=np.ascontiguousarray(X[:,keep])
    rng=np.random.default_rng(seed);x=np.ascontiguousarray(rng.standard_normal(A.shape[1]))
    b=np.ascontiguousarray(A@x)
    return A,b,x

def standard_cases():
    yield 'random64', make_random(32768,64,64,101)
    yield 'grouped64', make_grouped(65536,64,64,102)
    yield 'rankdef64', make_random(32768,64,56,103)
    yield 'inconsistent64', make_grouped(32768,64,64,104,True)
    yield 'digits', make_digits(105)
    yield 'random128', make_random(32768,128,128,106)
    yield 'grouped256', make_grouped(32768,256,256,107)
    yield 'rankdef256', make_random(16384,256,240,108)
    yield 'random512', make_random(4096,512,512,109)

def run_standard(L,omp):
    rows=[]
    for name,(A,b,x) in standard_cases():
        tr,ro,_=med_router(L,A,b,x,omp=omp)
        ts,so,_=med_seq(L,A,b,x)
        rr={
          'case':name,'m':int(A.shape[0]),'n':int(A.shape[1]),
          'reference_ms':1e3*ts,'router_ms':1e3*tr,'speedup':ts/tr if tr else None,
          'reference_class':CLS.get(int(so[0]),str(int(so[0]))),'reference_rank':int(so[1]),
          'router_class':STATUS.get(int(ro[0]),str(int(ro[0]))),'router_rank':int(ro[2]),
          'rank_lo':int(ro[3]),'rank_hi':int(ro[4]),'router_relres':None if not np.isfinite(ro[5]) else float(ro[5]),
          'quality_eta_x':None if not np.isfinite(ro[10]) else float(ro[10]),'fallback':bool(ro[8])}
        rows.append(rr); print('STD',rr,flush=True)
        del A,b,x
    sp=np.array([r['speedup'] for r in rows if r['speedup'] and r['speedup']>0])
    return {'rows':rows,'geomean_speedup':float(np.exp(np.mean(np.log(sp)))),'median_speedup':float(np.median(sp))}

def make_rank_transition(eps,seed,m=512,n=256):
    rng=np.random.default_rng(seed);hh=H(n)
    # 255 exact directions, each repeated; the last row introduces h_255 weakly.
    idx=np.arange(m)%255
    A=np.ascontiguousarray(hh[idx].copy())
    # Make the weak row late so it exercises closure/tail logic.
    A[-1]=hh[0]+eps*hh[255]
    x=rng.standard_normal(n); x-=np.dot(x,hh[255])*hh[255]  # no RHS signal in weak direction
    x=np.ascontiguousarray(x);b=np.ascontiguousarray(A@x)
    return A,b,x

def run_rank_transition(L,omp):
    levels=[1e-8,3e-9,1e-9,3e-10,3e-11,1e-12]
    out=[]
    for e in levels:
        states={};ranks={};maxrr=0; source=[]
        for seed in range(20):
            A,b,x=make_rank_transition(e,7000+seed)
            o=router(L,A,b,x,seed=8000+seed,omp=omp)
            key=STATUS.get(int(o[0]),str(int(o[0]))); states[key]=states.get(key,0)+1
            ranks[int(o[2])]=ranks.get(int(o[2]),0)+1
            if np.isfinite(o[5]): maxrr=max(maxrr,float(o[5]))
            source.append([int(o[3]),int(o[4])])
        row={'eps':e,'states':states,'ranks':ranks,'rank_intervals':source,'max_relres':maxrr}
        out.append(row); print('RANKTRANS',row,flush=True)
    return out

def run_guard_timing(L,omp):
    cases=[(2000,64,63),(10000,64,63),(50000,64,63),(5000,96,95),(20000,96,95),(10000,64,32),(10000,64,1),(512,192,191)]
    out=[]
    for m,n,r in cases:
        A,b,x=make_integer_rank(m,n,r,12000+m+n+r)
        L.bsolve_fg_counters_reset_api();
        tr,o,_=med_router(L,A,b,x,omp=omp,warm=3,reps=9)
        ctr=(ctypes.c_ulonglong*3)();L.bsolve_fg_counters_api(ctr)
        row={'m':m,'n':n,'r':r,'router_ms':tr*1e3,'status':STATUS.get(int(o[0])),'rank':int(o[2]),
             'fg_checks':int(ctr[0]),'fg_escalations':int(ctr[1]),'source_qrcp':int(ctr[2])}
        out.append(row); print('GUARD',row,flush=True)
    return out

def run_scaling(L):
    # Use three representative evidence-heavy cases; report router wall time relative to OMP=1.
    cases=[]
    for name,m,n,r,kind in [('grouped64',65536,64,64,'g'),('rankdef64',32768,64,56,'r'),('grouped256',32768,256,256,'g')]:
        A,b,x=make_grouped(m,n,r,13000) if kind=='g' else make_random(m,n,r,13001)
        cases.append((name,A,b,x))
    res={}
    for t in [1,2,4]:
        vals=[]; per=[]
        for name,A,b,x in cases:
            med,o,_=med_router(L,A,b,x,omp=t,warm=3,reps=9,seed=14000)
            vals.append(med);per.append({'case':name,'ms':med*1e3,'status':STATUS.get(int(o[0])),'rank':int(o[2])})
        if t==1: base=vals
        speed=[b/v for b,v in zip(base,vals)]
        res[str(t)]={'per_case':per,'geomean_vs_1':float(np.exp(np.mean(np.log(speed)))),'median_vs_1':float(np.median(speed))}
        print('SCALING',t,res[str(t)],flush=True)
    return res

def make_structured_rank(m,n,r,seed=21,scale_rows=False):
    rng=np.random.default_rng(seed);hh=H(n)
    A=np.empty((m,n),np.float64)
    q=min(r,m);A[:q]=hh[:q]
    if m>q:
        z=m-q
        idx=rng.integers(0,r,size=(z,4))
        sg=rng.choice(np.array([-1.0,1.0]),size=(z,4))
        A[q:]=(sg[:,0,None]*hh[idx[:,0]]+sg[:,1,None]*hh[idx[:,1]]+sg[:,2,None]*hh[idx[:,2]]+sg[:,3,None]*hh[idx[:,3]])*0.5
    x=np.ascontiguousarray(rng.standard_normal(n));b=np.ascontiguousarray(A@x)
    if scale_rows:
        ex=rng.uniform(-8,8,size=m);sc=np.ascontiguousarray(10.0**ex)
        A=np.ascontiguousarray(A*sc[:,None]);b=np.ascontiguousarray(b*sc)
    else:A=np.ascontiguousarray(A)
    return A,b,x

def make_late_growth(m,n,r0,seed=22,delay=False):
    rng=np.random.default_rng(seed);hh=H(n);A=np.empty((m,n),np.float64)
    prefix=min(n,m)
    idx0=np.arange(prefix)%max(r0,1);A[:prefix]=hh[idx0]
    pos=prefix
    if delay:
        hold=max(0,m-n-prefix);end=min(m,pos+hold);A[pos:end]=hh[0];pos=end
    for d in range(r0,n):
        if pos>=m:break
        A[pos]=hh[d];pos+=1
    if pos<m:
        ids=rng.integers(0,n,size=m-pos);A[pos:]=hh[ids]
    x=np.ascontiguousarray(rng.standard_normal(n));b=np.ascontiguousarray(A@x)
    return np.ascontiguousarray(A),b,x

def structural_cases():
    cases=[]
    # 30 size/tallness/rank cases.
    for n in [32,64,128,256,512]:
        for mult in [4,16,64]:
            m=n*mult
            cases.append((f'full_n{n}_x{mult}',*make_structured_rank(m,n,n,20000+n+mult), 'unique',n))
            r=n-max(1,n//8)
            cases.append((f'def_n{n}_x{mult}',*make_structured_rank(m,n,r,21000+n+mult), 'infinite',r))
    # 6 late-growth cases in a common dimension.
    for r0 in [1,2,4,8,16,64]:
        cases.append((f'late_n128_r0_{r0}',*make_late_growth(4096,128,r0,22000+r0,False),'unique',128))
    # 2 strongly delayed growth cases.
    cases.append(('delayed_n64',*make_late_growth(8192,64,1,23001,True),'unique',64))
    cases.append(('delayed_n128',*make_late_growth(8192,128,2,23002,True),'unique',128))
    # 2 exact-rank constructions with injected contradiction.
    for n in [64,128]:
        A,b,x=make_structured_rank(4096,n,n,24000+n);b=b.copy();b[-1]+=0.25
        cases.append((f'inconsistent_n{n}',A,b,x,'inconsistent',n))
    # 4 row-scaled cases.
    for n,r in [(64,64),(64,56),(128,128),(128,112)]:
        A,b,x=make_structured_rank(4096,n,r,25000+n+r,True)
        cases.append((f'scaled_n{n}_r{r}',A,b,x,'unique' if r==n else 'infinite',r))
    assert len(cases)==44,len(cases)
    return cases

def run_structural(L,omp):
    rows=[];wrong=[];maxrr=0.0;times=[]
    for ci,(name,A,b,x,expect_cls,expect_rank) in enumerate(structural_cases()):
        per=[]
        for si,seed in enumerate([31001,31002,31003]):
            o=router(L,A,b,x,seed=seed+ci*17,omp=omp)
            got_cls=STATUS.get(int(o[0]),str(int(o[0]))); got_rank=int(o[2]);rr=None if not np.isfinite(o[5]) else float(o[5])
            ok=(got_cls==expect_cls and (expect_cls=='inconsistent' or got_rank==expect_rank))
            if not ok: wrong.append({'case':name,'seed':seed,'expected':[expect_cls,expect_rank],'got':[got_cls,got_rank,int(o[3]),int(o[4])]})
            if rr is not None and expect_cls!='inconsistent':maxrr=max(maxrr,rr)
            times.append(float(o[7])); per.append({'seed':seed,'class':got_cls,'rank':got_rank,'lo':int(o[3]),'hi':int(o[4]),'ms':1e3*float(o[7]),'relres':rr,'ok':ok})
        rows.append({'case':name,'m':int(A.shape[0]),'n':int(A.shape[1]),'expected_class':expect_cls,'expected_rank':expect_rank,'runs':per})
        print('STRUCT',name,'ok',all(z['ok'] for z in per),'ms',round(float(np.median([z['ms'] for z in per])),3),flush=True)
        del A,b,x
    return {'instances':44,'routing_seeds_per_instance':3,'checks':132,'hard_failures':len(wrong),'failures':wrong,
            'max_consistent_relres':maxrr,'median_router_ms':float(np.median(times)*1e3),'rows':rows}


def lapack_gelsy(L,A,b,x):
    omp_threads(1);out=np.zeros(7,np.float64);L.bsolve_lapack_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],ptr(out));return out

def end2end_ms(fn,warm=2,reps=7):
    for _ in range(warm):fn()
    t=[];last=None
    for _ in range(reps):
        q=time.perf_counter_ns();last=fn();t.append((time.perf_counter_ns()-q)*1e-6)
    return float(np.median(t)),last,t

def run_lapack_context(L,omp):
    rows=[]
    # A representative subset spanning full rank, deficient rank, redundancy, and size.
    specs=[
      ('random64',lambda:make_random(32768,64,64,101)),
      ('grouped64',lambda:make_grouped(65536,64,64,102)),
      ('rankdef64',lambda:make_random(32768,64,56,103)),
      ('random128',lambda:make_random(32768,128,128,106)),
      ('rankdef256',lambda:make_random(16384,256,240,108)),
      ('random512',lambda:make_random(4096,512,512,109)),
    ]
    for name,maker in specs:
        A,b,x=maker()
        rt,ro,_=end2end_ms(lambda:router(L,A,b,x,seed=47001,omp=omp),2,7)
        lt,lo,_=end2end_ms(lambda:lapack_gelsy(L,A,b,x),2,7)
        row={'case':name,'m':A.shape[0],'n':A.shape[1],'router_ms':rt,'dgelsy_ms':lt,'dgelsy_over_router':lt/rt,
             'router_class':STATUS.get(int(ro[0])),'router_rank':int(ro[2]),'router_relres':None if not np.isfinite(ro[5]) else float(ro[5]),
             'dgelsy_class':CLS.get(int(lo[0])),'dgelsy_rank':int(lo[1]),'dgelsy_relres':float(lo[5])}
        rows.append(row);print('LAPACK',row,flush=True);del A,b,x
    return rows


def env_info():
    try: cpu=subprocess.check_output(['bash','-lc',"lscpu | grep -m1 'Model name:' | sed 's/Model name:[[:space:]]*//'"],text=True).strip()
    except Exception: cpu='unknown'
    return {'cpu':cpu,'cpus':os.cpu_count(),'platform':platform.platform(),'python':platform.python_version(),
            'numpy':np.__version__,'threadpools':threadpool_info()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--omp',type=int,default=4);ap.add_argument('--out',default=str(ROOT/'results'/'numerical_rerun.json'))
    ap.add_argument('--sections',default='standard,rank,guard,scaling')
    a=ap.parse_args(); L=load(); sections=set(x.strip() for x in a.sections.split(',') if x.strip())
    out={'environment':env_info(),'omp_router':a.omp,'blas_threads':1,'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    with threadpool_limits(limits=1,user_api='blas'):
        if 'standard' in sections: out['standard']=run_standard(L,a.omp)
        if 'rank' in sections: out['rank_transition']=run_rank_transition(L,a.omp)
        if 'guard' in sections: out['guard_timing']=run_guard_timing(L,a.omp)
        if 'scaling' in sections: out['scaling']=run_scaling(L)
        if 'structural' in sections: out['structural']=run_structural(L,a.omp)
        if 'lapack' in sections: out['lapack_context']=run_lapack_context(L,a.omp)
    Path(a.out).write_text(json.dumps(out,indent=2))
    print('WROTE',a.out)
if __name__=='__main__': main()
