#!/usr/bin/env python3
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','4')
import ctypes, json, math, time, subprocess, platform
from pathlib import Path
import numpy as np
from scipy.special import sph_harm_y
from scipy.ndimage import gaussian_filter
from threadpoolctl import threadpool_limits, threadpool_info

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'libaffine_bundle_solver.so'
DP=ctypes.POINTER(ctypes.c_double)
STATUS={1:'unique',2:'infinite',3:'inconsistent',4:'undecidable'}
CLS={1:'unique',2:'infinite',3:'inconsistent',4:'fail',5:'undecidable'}

def ptr(a): return a.ctypes.data_as(DP)

def load():
    L=ctypes.CDLL(str(LIB))
    sig=[DP,DP,DP,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulonglong,ctypes.c_int,DP]
    L.bsolve_router_meta_api.argtypes=sig
    L.bsolve_global_qr_api.argtypes=sig
    L.bsolve_lapack_api.argtypes=[DP,DP,DP,ctypes.c_int,ctypes.c_int,DP]
    return L

LIBGOMP=None
try:
    LIBGOMP=ctypes.CDLL('libgomp.so.1'); LIBGOMP.omp_set_num_threads.argtypes=[ctypes.c_int]
except OSError: pass

def omp_threads(k):
    if LIBGOMP is not None: LIBGOMP.omp_set_num_threads(int(k))

def router(L,A,b,x,seed=91001,omp=4):
    omp_threads(omp); out=np.zeros(11,np.float64)
    L.bsolve_router_meta_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],1,2,2,int(seed),0,ptr(out))
    return out

def global_qr(L,A,b,x,seed=92001,omp=4):
    omp_threads(omp); out=np.zeros(7,np.float64)
    L.bsolve_global_qr_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],1,2,2,int(seed),0,ptr(out))
    return out

def dgelsy(L,A,b,x):
    omp_threads(1); out=np.zeros(7,np.float64)
    L.bsolve_lapack_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],ptr(out)); return out

def med_call(fn,warm=2,reps=7):
    for _ in range(warm): fn()
    ts=[]; last=None
    for _ in range(reps):
        t0=time.perf_counter_ns(); last=fn(); ts.append((time.perf_counter_ns()-t0)*1e-6)
    return float(np.median(ts)), last, ts

def record_methods(L,A,b,x,seed=91001,do_global=True,do_lapack=True):
    rt,ro,rts=med_call(lambda:router(L,A,b,x,seed,4),2,7)
    out={'router_ms':rt,'router_class':STATUS.get(int(ro[0]),str(int(ro[0]))),'router_rank':int(ro[2]),
         'rank_lo':int(ro[3]),'rank_hi':int(ro[4]),'router_relres':None if not np.isfinite(ro[5]) else float(ro[5]),
         'router_eta_x':None if not np.isfinite(ro[10]) else float(ro[10])}
    if do_global:
        gt,go,gts=med_call(lambda:global_qr(L,A,b,x,seed+123,4),2,5)
        out.update(global_ms=gt,global_class=CLS.get(int(go[0]),str(int(go[0]))),global_rank=int(go[1]),
                   global_relres=None if not np.isfinite(go[5]) else float(go[5]))
    if do_lapack:
        lt,lo,lts=med_call(lambda:dgelsy(L,A,b,x),1,5)
        out.update(dgelsy_ms=lt,dgelsy_class=CLS.get(int(lo[0]),str(int(lo[0]))),dgelsy_rank=int(lo[1]),
                   dgelsy_relres=None if not np.isfinite(lo[5]) else float(lo[5]))
    return out

# ---------- Radio phase calibration ----------
def radio_complete(N, reference=False, inconsistent=False, seed=1):
    # One equation for each unordered baseline i<j: phi_i-phi_j=d_ij.
    # A reference row phi_0 = truth_0 removes the one-dimensional gauge.
    rng=np.random.default_rng(seed); x=rng.standard_normal(N)
    m=N*(N-1)//2 + (1 if reference else 0)
    A=np.zeros((m,N),np.float64); b=np.empty(m,np.float64)
    k=0
    for i in range(N):
        for j in range(i+1,N):
            A[k,i]=1.0; A[k,j]=-1.0; b[k]=x[i]-x[j]; k+=1
    if reference:
        A[k,0]=1.0; b[k]=x[0]; k+=1
    if inconsistent:
        # A duplicate closure equation with changed RHS would be the cleanest contradiction.
        # Replace the last baseline by a duplicate of the first and perturb its RHS.
        # Append it, preserving exact rank N-1.
        A=np.vstack([A,A[0:1]])
        b=np.concatenate([b,np.array([b[0]+0.25])])
    return np.ascontiguousarray(A),np.ascontiguousarray(b),np.ascontiguousarray(x)

def radio_disconnected(N, seed=2):
    rng=np.random.default_rng(seed); x=rng.standard_normal(N); split=N//2
    edges=[]
    for lo,hi in [(0,split),(split,N)]:
        for i in range(lo,hi):
            for j in range(i+1,hi): edges.append((i,j))
    A=np.zeros((len(edges),N),np.float64);b=np.empty(len(edges),np.float64)
    for k,(i,j) in enumerate(edges): A[k,i]=1.;A[k,j]=-1.;b[k]=x[i]-x[j]
    return np.ascontiguousarray(A),np.ascontiguousarray(b),np.ascontiguousarray(x)

def run_radio(L):
    specs=[('N64_gauge',*radio_complete(64,False,False,1001),'infinite',63),
           ('N64_reference',*radio_complete(64,True,False,1002),'unique',64),
           ('N128_gauge',*radio_complete(128,False,False,1003),'infinite',127),
           ('N128_disconnected',*radio_disconnected(128,1004),'infinite',126),
           ('N256_gauge',*radio_complete(256,False,False,1005),'infinite',255),
           ('N256_inconsistent',*radio_complete(256,False,True,1006),'inconsistent',255)]
    rows=[]
    for q,(name,A,b,x,ec,er) in enumerate(specs):
        z=record_methods(L,A,b,x,93000+q,do_global=False,do_lapack=(A.shape[1]<=128))
        ok=(z['router_class']==ec and (ec=='inconsistent' or z['router_rank']==er))
        row={'case':name,'m':A.shape[0],'n':A.shape[1],'expected_class':ec,'expected_rank':er,'ok':ok,**z}
        rows.append(row); print('RADIO',row,flush=True); del A,b,x
    return {'construction':'complete undirected incidence; one optional reference; one duplicate perturbed equation for contradiction','rows':rows,'hard_failures':sum(not r['ok'] for r in rows)}

# ---------- Real spherical harmonics ----------
def real_sh_matrix(L, theta, phi):
    theta=np.asarray(theta);phi=np.asarray(phi); cols=[]
    for ell in range(L+1):
        # m=0 first
        y=sph_harm_y(ell,0,theta,phi)
        cols.append(np.asarray(y.real,np.float64))
        for m in range(1,ell+1):
            y=sph_harm_y(ell,m,theta,phi)
            # Any fixed real normalization preserves rank; use orthonormal real convention.
            f=math.sqrt(2.0)*((-1.0)**m)
            cols.append(np.asarray(f*y.real,np.float64))
            cols.append(np.asarray(f*y.imag,np.float64))
    return np.ascontiguousarray(np.column_stack(cols))

def make_harmonic(L,m,kind,seed):
    rng=np.random.default_rng(seed)
    if kind=='full':
        u=rng.uniform(-1,1,size=m); theta=np.arccos(u); phi=rng.uniform(0,2*np.pi,size=m)
    elif kind=='equator':
        theta=np.full(m,np.pi/2); phi=rng.uniform(0,2*np.pi,size=m)
    else: raise ValueError(kind)
    A=real_sh_matrix(L,theta,phi); n=A.shape[1]
    x=np.ascontiguousarray(rng.standard_normal(n)); b=np.ascontiguousarray(A@x)
    return A,b,x

def run_harmonic(Lib):
    rows=[]
    for ell,m in [(7,4096),(11,8192),(15,16384)]:
        for kind in ('full','equator'):
            A,b,x=make_harmonic(ell,m,kind,2000+ell+(0 if kind=='full' else 100))
            expect=nexp=(ell+1)**2 if kind=='full' else 1+2*ell
            ec='unique' if kind=='full' else 'infinite'
            z=record_methods(Lib,A,b,x,94000+ell+(0 if kind=='full' else 1),do_global=True,do_lapack=True)
            ok=(z['router_class']==ec and z['router_rank']==expect)
            row={'case':f'L{ell}_{kind}','L':ell,'m':m,'n':A.shape[1],'expected_class':ec,'expected_rank':expect,'ok':ok,**z}
            rows.append(row); print('HARM',row,flush=True); del A,b,x
    # permutation robustness on the largest full-sky fixed matrix
    A,b,x=make_harmonic(15,16384,'full',2015); rng=np.random.default_rng(2999); per=[]
    for k in range(12):
        p=rng.permutation(A.shape[0]); Ap=np.ascontiguousarray(A[p]);bp=np.ascontiguousarray(b[p])
        o=router(Lib,Ap,bp,x,95000+k,4); per.append({'class':STATUS.get(int(o[0])),'rank':int(o[2]),'rr':None if not np.isfinite(o[5]) else float(o[5])})
    return {'rows':rows,'hard_failures':sum(not r['ok'] for r in rows),'L15_permutations':per}

# ---------- SIS-like semi-linear lens ----------
def lens_matrix(src_n, image_n, theta_E=0.38, src_extent=0.72, img_extent=1.35, psf_sigma=0.75):
    # Image-plane theta -> SIS-like beta = theta - theta_E theta/|theta|,
    # followed by bilinear interpolation on a regular source grid.
    xs=np.linspace(-src_extent,src_extent,src_n); ys=xs.copy(); h=xs[1]-xs[0]
    im=np.linspace(-img_extent,img_extent,image_n); xx,yy=np.meshgrid(im,im,indexing='xy')
    rr=np.hypot(xx,yy); fac=np.ones_like(rr); nz=rr>1e-15; fac[nz]=1.0-theta_E/rr[nz]
    bx=xx*fac; by=yy*fac
    u=(bx-xs[0])/h; v=(by-ys[0])/h
    i=np.floor(u).astype(int); j=np.floor(v).astype(int)
    inside=(i>=0)&(i<src_n-1)&(j>=0)&(j<src_n-1)
    i=np.clip(i,0,src_n-2);j=np.clip(j,0,src_n-2);du=u-i;dv=v-j
    m=image_n*image_n;n=src_n*src_n; A=np.zeros((m,n),np.float64); rows=np.arange(m); flat_inside=inside.ravel()
    ii=i.ravel(); jj=j.ravel(); du=du.ravel();dv=dv.ravel()
    for di,dj,w in [(0,0,(1-du)*(1-dv)),(1,0,du*(1-dv)),(0,1,(1-du)*dv),(1,1,du*dv)]:
        col=(jj+dj)*src_n+(ii+di); idx=rows[flat_inside]
        A[idx,col[flat_inside]] += w[flat_inside]
    if psf_sigma>0:
        for c in range(n): A[:,c]=gaussian_filter(A[:,c].reshape(image_n,image_n),psf_sigma,mode='constant').ravel()
    return np.ascontiguousarray(A)

def make_lens(src_n,image_n,seed):
    A=lens_matrix(src_n,image_n); rng=np.random.default_rng(seed); x=np.ascontiguousarray(rng.standard_normal(A.shape[1]));b=np.ascontiguousarray(A@x)
    return A,b,x

def normal_eq(A,b):
    # Full-rank solution-only contextual comparator; not a status/rank oracle.
    return np.linalg.solve(A.T@A,A.T@b)

def relres(A,b,x):
    return float(np.linalg.norm(A@x-b)/(np.linalg.norm(A)*np.linalg.norm(x)+np.linalg.norm(b)+1e-300))

def run_lens(L):
    rows=[]
    for q,(s,im) in enumerate([(8,64),(12,64),(16,96)]):
        A,b,x=make_lens(s,im,3000+s); z=record_methods(L,A,b,x,96000+q,do_global=True,do_lapack=True)
        nt,nx,_=med_call(lambda:normal_eq(A,b),1,5); nrr=relres(A,b,nx)
        ok=(z['router_class']=='unique' and z['router_rank']==s*s)
        row={'case':f'{s}x{s}_source','m':A.shape[0],'n':A.shape[1],'expected_class':'unique','expected_rank':s*s,'ok':ok,
             'normal_eq_ms':nt,'normal_eq_relres':nrr,**z}; rows.append(row); print('LENS',row,flush=True);del A,b,x
    # 12 deterministic row permutations of a full-coverage 12x12 case.
    A,b,x=make_lens(12,64,3012); rng=np.random.default_rng(3999); per=[]
    for k in range(12):
        p=rng.permutation(A.shape[0]); o=router(L,np.ascontiguousarray(A[p]),np.ascontiguousarray(b[p]),x,97000+k,4)
        per.append({'class':STATUS.get(int(o[0])),'rank':int(o[2]),'rr':None if not np.isfinite(o[5]) else float(o[5])})
    return {'rows':rows,'hard_failures':sum(not r['ok'] for r in rows),'row_permutations':per,
            'construction':{'lens':'SIS-like beta=theta-theta_E theta/|theta|','theta_E':0.38,'src_extent':0.72,'img_extent':1.35,'psf_sigma_pixels':0.75}}

def env():
    try: cpu=subprocess.check_output(['bash','-lc',"lscpu | grep -m1 'Model name:' | sed 's/Model name:[[:space:]]*//'"],text=True).strip()
    except Exception: cpu='unknown'
    return {'cpu':cpu,'cpus':os.cpu_count(),'platform':platform.platform(),'python':platform.python_version(),'numpy':np.__version__,'threadpools':threadpool_info()}

def main():
    L=load(); out={'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'environment':env(),'omp_router':4,'blas_threads':1}
    with threadpool_limits(limits=1,user_api='blas'):
        out['radio']=run_radio(L); out['harmonic']=run_harmonic(L); out['lens']=run_lens(L)
    p=ROOT/'results'/'applications_final.json';p.write_text(json.dumps(out,indent=2));print('WROTE',p)
if __name__=='__main__': main()
