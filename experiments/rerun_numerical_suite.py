#!/usr/bin/env python3
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','4')
os.environ.setdefault('VECLIB_MAXIMUM_THREADS','1')
import argparse, contextlib, ctypes, importlib.metadata, json, math, platform, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from scipy.linalg import hadamard
from threadpoolctl import threadpool_limits, threadpool_info

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from experiments import numerical_suite_contract as contract

DP=ctypes.POINTER(ctypes.c_double)
STATUS_CODES={1:'unique',2:'infinite',3:'inconsistent',4:'fail',5:'undecidable'}

def decode_status(value):
    code=int(value)
    if code not in STATUS_CODES:
        raise ValueError(f'unknown router status {code}')
    return STATUS_CODES[code]

def ptr(a): return a.ctypes.data_as(DP)

def load(source_state,lib_dir=None,cdll=ctypes.CDLL):
    return contract.resolve_and_load_router(
        root=ROOT,lib_dir=lib_dir or os.environ.get('ABS_LIB_DIR',ROOT),
        source_state=source_state,cdll=cdll)

@contextlib.contextmanager
def openmp_runtime_context(requested, *, strict,
                           limits_factory=threadpool_limits,
                           info_provider=threadpool_info):
    requested=int(requested)
    with limits_factory(limits=requested,user_api='openmp'):
        pools=contract.partition_threadpools(
            info_provider(),hash_libraries=False)['openmp_pools']
        reasons=[]
        if not pools:
            reasons.append('openmp_runtime_unavailable')
        elif len(pools)!=1:
            reasons.append('openmp_runtime_ambiguous')
        pool=pools[0] if len(pools)==1 else None
        observed=pool.get('num_threads') if pool else None
        if pool is not None and observed!=requested:
            reasons.append('openmp_requested_observed_mismatch')
        identity=None
        if pool is not None:
            identity={name:pool.get(name) for name in (
                'runtime_id','basename','user_api','internal_api','version')}
            if not all(isinstance(identity.get(name),str) and identity[name]
                       for name in ('runtime_id','basename','user_api',
                                    'internal_api')):
                reasons.append('openmp_runtime_identity_incomplete')
        observation={'valid':not reasons,'reasons':reasons,
          'requested_num_threads':requested,'observed_num_threads':observed,
          'runtime_identity':identity}
        if strict and reasons:
            raise RuntimeError(','.join(reasons))
        yield observation

def router(L,A,b,x,seed=777,omp=4,*,candidate=False,
           runtime_context=openmp_runtime_context):
    contract.ensure_abi_arrays(A,b,x)
    with runtime_context(omp,strict=candidate) as observation:
        out=np.zeros(11,np.float64)
        L.bsolve_router_meta_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],
                                 1,2,2,int(seed),0,ptr(out))
    decode_status(out[0])
    return out,observation

def seq(L,A,b,x):
    contract.ensure_abi_arrays(A,b,x)
    out=np.zeros(7,np.float64)
    L.bsolve_seq_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],ptr(out))
    return out

def med_router(L,A,b,x,*,case_id,generator_seed,omp=4,warm=4,reps=11,
               warmup_seeds=(),source='solver-reported',candidate=False,
               runtime_context=openmp_runtime_context):
    spec=contract.CANONICAL_CASES_BY_ID[case_id]
    run_contract=spec['run_contract']
    warmup_seeds=list(warmup_seeds)
    if warmup_seeds!=run_contract['warmup_routing_seeds'] or \
            len(warmup_seeds)!=warm or reps!=len(run_contract['routing_seeds']):
        raise ValueError(f'configured run shape differs from protocol: {case_id}')
    for routing_seed in warmup_seeds:
        router(L,A,b,x,routing_seed,omp,candidate=candidate,
               runtime_context=runtime_context)
    values=[];last=None;runs=[]
    for repetition_index,routing_seed in enumerate(run_contract['routing_seeds']):
        started=time.perf_counter_ns()
        last,observation=router(
            L,A,b,x,routing_seed,omp,candidate=candidate,
            runtime_context=runtime_context)
        wall_seconds=(time.perf_counter_ns()-started)*1e-9
        duration=float(last[7]) if source=='solver-reported' else wall_seconds
        diagnostics=_diagnostics(last)
        numerical=_numerical(case_id,diagnostics['status'],diagnostics['rank'],
                             diagnostics['rank_lo'],diagnostics['rank_hi'])
        values.append(duration)
        runs.append({
          'run_id':run_contract['run_id_format'].format(
              case_id=case_id,repetition_index=repetition_index),
          'case_id':case_id,'generator_seed':int(generator_seed),
          'routing_seed':int(routing_seed),'repetition_index':repetition_index,
          'requested_omp_threads':int(omp),
          'observed_omp_threads':observation['observed_num_threads'],
          'openmp_runtime_identity':observation['runtime_identity'],
          'duration':{'value':duration,'unit':'s'},
          'diagnostics':diagnostics,'numerical_contract':numerical})
    return float(np.median(values)),last,values,runs

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

def _input(case_id,A,b,x,seed):
    spec=contract.CANONICAL_CASES_BY_ID[case_id]
    return contract.describe_input(A,b,x,generator=spec['generator'],seed=seed)

def _diagnostics(o):
    return {'status':decode_status(o[0]),'rank':int(o[2]),
            'rank_lo':int(o[3]),'rank_hi':int(o[4]),
            'router_relres':None if not np.isfinite(o[5]) else float(o[5]),
            'router_berr':None if not np.isfinite(o[10]) else float(o[10]),
            'fallback':bool(o[8]),'solver_seconds':float(o[7])}

def _numerical(case_id,status,rank,lo=None,hi=None):
    spec=contract.CANONICAL_CASES_BY_ID[case_id]
    expected={'status':spec['expected_status'],'rank':spec['expected_rank']}
    actual={'status':status,'rank':int(rank)}
    reasons=[]
    if status!=spec['expected_status']:
        reasons.append('status_mismatch')
    if int(rank)!=spec['expected_rank']:
        reasons.append('rank_mismatch')
    if spec['section']=='rank':
        expected['rank_interval']=[spec['expected_rank_lo'],spec['expected_rank_hi']]
        actual['rank_interval']=[int(lo),int(hi)]
        if actual['rank_interval']!=expected['rank_interval']:
            reasons.append('rank_interval_mismatch')
    return {'expected':expected,'actual':actual,'valid':not reasons,'reasons':reasons}

def _ratio(case_id,numerator,denominator):
    required=contract.CANONICAL_CASES_BY_ID[case_id]['required_ratios']
    if len(required)!=1:
        raise ValueError(f'case does not define exactly one ratio: {case_id}')
    return {**required[0],'value':float(numerator)/float(denominator)}

def _aggregate_runs(case_id,runs):
    spec=contract.CANONICAL_CASES_BY_ID[case_id]
    failures=[run['run_id'] for run in runs
              if not run['numerical_contract']['valid']]
    diagnostics={**runs[-1]['diagnostics']} if runs else {}
    numerical=_numerical(case_id,diagnostics.get('status','missing'),
                         diagnostics.get('rank',-1),
                         diagnostics.get('rank_lo'),diagnostics.get('rank_hi'))
    if failures:
        numerical['valid']=False
        numerical['reasons'].extend(f'run_failed:{run_id}' for run_id in failures)
    return diagnostics,numerical

def _section(section_id,cases,summary=None):
    output=dict(contract.CANONICAL_SECTIONS)[section_id]
    details={'case_count':len(cases)}
    if summary: details.update(summary)
    return {'section_id':section_id,'output_name':output,
            'cases':cases,'summary':details}

def run_standard(L,omp,*,candidate=False):
    rows=[]
    for name,(A,b,x) in standard_cases():
        case_id=f'standard.{name}'
        generator_seed=contract.CANONICAL_CASES_BY_ID[case_id]['input_seeds'][0]
        tr,ro,traw,runs=med_router(
            L,A,b,x,case_id=case_id,generator_seed=generator_seed,omp=omp,
            warm=4,reps=11,warmup_seeds=range(777,781),candidate=candidate)
        ts,so,sraw=med_seq(L,A,b,x)
        diag,numerical=_aggregate_runs(case_id,runs)
        diag['sequential_reference']={
            'status':decode_status(so[0]),
            'rank':int(so[1]),'relres':None if not np.isfinite(so[5]) else float(so[5]),
            'solver_seconds':float(so[4])}
        rr={'case_id':case_id,'inputs':[_input(case_id,A,b,x,generator_seed)],
            'timings':[
              contract.timing_record(operation='router',source='solver-reported',
                warmups=4,repetitions=11,raw=traw),
              contract.timing_record(operation='sequential_reference',
                source='solver-reported',warmups=2,repetitions=7,raw=sraw)],
            'ratios':[_ratio(case_id,ts,tr)],'runs':runs,
            'diagnostics':diag,
            'numerical_contract':numerical,
            'observations':{'timing_range':'not-evaluated'}}
        rows.append(rr); print('STD',rr,flush=True)
        del A,b,x
    sp=np.array([r['ratios'][0]['value'] for r in rows])
    return _section('standard',rows,{
        'ratio_name':'sequential_reference_over_router','ratio_count':len(sp),
        'ratio_geomean':float(np.exp(np.mean(np.log(sp)))),
        'ratio_median':float(np.median(sp))})

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

def run_rank_transition(L,omp,*,candidate=False):
    levels=[1e-8,3e-9,1e-9,3e-10,3e-11,1e-12]
    out=[]
    for e in levels:
        case_id=f'rank.eps_{format(e,".0e")}'
        states={};ranks={};residuals=[]; intervals=[];inputs=[];runs=[];raw=[]
        spec=contract.CANONICAL_CASES_BY_ID[case_id]
        run_contract=spec['run_contract']
        for repetition_index,(input_seed,routing_seed) in enumerate(zip(
                run_contract['generator_seeds'],run_contract['routing_seeds'])):
            A,b,x=make_rank_transition(e,input_seed)
            inputs.append(_input(case_id,A,b,x,input_seed))
            o,observation=router(L,A,b,x,seed=routing_seed,omp=omp,
                                 candidate=candidate)
            diag=_diagnostics(o);key=diag['status'];states[key]=states.get(key,0)+1
            ranks[int(o[2])]=ranks.get(int(o[2]),0)+1
            rr=None if not np.isfinite(o[5]) else float(o[5])
            if rr is not None: residuals.append(rr)
            intervals.append([int(o[3]),int(o[4])]);raw.append(float(o[7]))
            run_numerical=_numerical(case_id,key,int(o[2]),int(o[3]),int(o[4]))
            runs.append({'case_id':case_id,
              'run_id':run_contract['run_id_format'].format(
                  case_id=case_id,repetition_index=repetition_index),
              'generator_seed':input_seed,'routing_seed':routing_seed,
              'repetition_index':repetition_index,
              'requested_omp_threads':omp,
              'observed_omp_threads':observation['observed_num_threads'],
              'openmp_runtime_identity':observation['runtime_identity'],
              'duration':{'value':float(o[7]),'unit':'s'},
              'diagnostics':diag,'numerical_contract':run_numerical})
        unanimous=(states=={spec['expected_status']:20} and
                   ranks=={spec['expected_rank']:20} and
                   all(pair==[spec['expected_rank_lo'],spec['expected_rank_hi']]
                       for pair in intervals))
        status=spec['expected_status'] if states=={spec['expected_status']:20} else 'mixed'
        rank=spec['expected_rank'] if ranks=={spec['expected_rank']:20} else next(iter(ranks))
        lo=min(pair[0] for pair in intervals);hi=max(pair[1] for pair in intervals)
        numerical=_numerical(case_id,status,rank,lo,hi)
        if not unanimous and not numerical['reasons']:
            numerical['reasons'].append('run_outcome_mismatch');numerical['valid']=False
        failed=[run['run_id'] for run in runs
                if not run['numerical_contract']['valid']]
        if failed:
            numerical['valid']=False
            numerical['reasons'].extend(f'run_failed:{run_id}' for run_id in failed)
        row={'case_id':case_id,'inputs':inputs,
             'timings':[contract.timing_record(operation='router',
               source='solver-reported',warmups=0,repetitions=20,raw=raw)],
             'ratios':[],'runs':runs,
             'diagnostics':{'status':status,'rank':int(rank),'rank_lo':lo,'rank_hi':hi,
               'router_relres':max(residuals) if residuals else None,
               'router_berr':None,'finite_residual_count':len(residuals),
               'states':states,'ranks':{str(k):v for k,v in ranks.items()},
               'rank_intervals':intervals},
             'numerical_contract':numerical,
             'observations':{'timing_range':'not-evaluated','epsilon':e}}
        out.append(row); print('RANKTRANS',row,flush=True)
    return _section('rank',out)

def run_guard_timing(L,omp,*,candidate=False):
    cases=[(2000,64,63),(10000,64,63),(50000,64,63),(5000,96,95),(20000,96,95),(10000,64,32),(10000,64,1),(512,192,191)]
    out=[]
    for m,n,r in cases:
        seed=12000+m+n+r;case_id=f'guard.{m}x{n}.r{r}'
        A,b,x=make_integer_rank(m,n,r,seed)
        L.bsolve_fg_counters_reset_api();
        tr,o,raw,runs=med_router(
            L,A,b,x,case_id=case_id,generator_seed=seed,omp=omp,warm=3,
            reps=9,warmup_seeds=range(777,780),candidate=candidate)
        ctr=(ctypes.c_ulonglong*3)();L.bsolve_fg_counters_api(ctr)
        diag,numerical=_aggregate_runs(case_id,runs);diag.update({'fg_checks':int(ctr[0]),
             'fg_escalations':int(ctr[1]),'source_qrcp':int(ctr[2])})
        row={'case_id':case_id,'inputs':[_input(case_id,A,b,x,seed)],
             'timings':[contract.timing_record(operation='router',
               source='solver-reported',warmups=3,repetitions=9,raw=raw)],
             'ratios':[],'runs':runs,'diagnostics':diag,
             'numerical_contract':numerical,
             'observations':{'timing_range':'not-evaluated'}}
        out.append(row); print('GUARD',row,flush=True)
    return _section('guard',out)

def run_scaling(L,*,candidate=False):
    # Use three representative evidence-heavy cases; report router wall time relative to OMP=1.
    cases=[]
    for name,m,n,r,kind in [('grouped64',65536,64,64,'g'),('rankdef64',32768,64,56,'r'),('grouped256',32768,256,256,'g')]:
        A,b,x=make_grouped(m,n,r,13000) if kind=='g' else make_random(m,n,r,13001)
        cases.append((name,A,b,x))
    rows=[];base={}
    for t in [1,2,4]:
        vals=[]
        for name,A,b,x in cases:
            case_id=f'scaling.omp{t}.{name}'
            seed=contract.CANONICAL_CASES_BY_ID[case_id]['input_seeds'][0]
            med,o,raw,runs=med_router(
                L,A,b,x,case_id=case_id,generator_seed=seed,omp=t,warm=3,
                reps=9,warmup_seeds=range(14000,14003),candidate=candidate)
            vals.append(med)
            if t==1: base[name]=med
            diag,numerical=_aggregate_runs(case_id,runs)
            ratio=_ratio(case_id,base[name],med)
            row={'case_id':case_id,'inputs':[_input(case_id,A,b,x,seed)],
                 'timings':[contract.timing_record(operation='router',
                    source='solver-reported',warmups=3,repetitions=9,raw=raw)],
                 'ratios':[ratio],'runs':runs,'diagnostics':diag,
                 'numerical_contract':numerical,
                 'observations':{'timing_range':'not-evaluated','omp_threads':t}}
            rows.append(row);print('SCALING',t,row,flush=True)
    speed=[row['ratios'][0]['value'] for row in rows]
    return _section('scaling',rows,{'ratio_name':'one_thread_router_over_router',
      'ratio_count':len(speed),'ratio_geomean':float(np.exp(np.mean(np.log(speed)))),
      'ratio_median':float(np.median(speed))})

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

def run_structural(L,omp,*,candidate=False):
    rows=[];wrong=[];residuals=[];times=[]
    for ci,(name,A,b,x,expect_cls,expect_rank) in enumerate(structural_cases()):
        case_id=f'structural.{name}';spec=contract.CANONICAL_CASES_BY_ID[case_id]
        input_seed=spec['input_seeds'][0];per=[];raw=[]
        for repetition_index,adjusted_seed in enumerate(
                spec['run_contract']['routing_seeds']):
            o,observation=router(L,A,b,x,seed=adjusted_seed,omp=omp,
                                 candidate=candidate)
            diag=_diagnostics(o);got_cls=diag['status'];got_rank=int(o[2]);rr=None if not np.isfinite(o[5]) else float(o[5])
            ok=(got_cls==expect_cls and got_rank==expect_rank)
            if not ok: wrong.append({'case_id':case_id,'seed':adjusted_seed,
              'expected':[expect_cls,expect_rank],
              'got':[got_cls,got_rank,int(o[3]),int(o[4])]})
            if rr is not None and expect_cls!='inconsistent':residuals.append(rr)
            raw.append(float(o[7]));times.append(float(o[7]))
            per.append({'case_id':case_id,
              'run_id':spec['run_contract']['run_id_format'].format(
                  case_id=case_id,repetition_index=repetition_index),
              'generator_seed':input_seed,'routing_seed':adjusted_seed,
              'repetition_index':repetition_index,
              'requested_omp_threads':omp,
              'observed_omp_threads':observation['observed_num_threads'],
              'openmp_runtime_identity':observation['runtime_identity'],
              'duration':{'value':float(o[7]),'unit':'s'},
              'diagnostics':diag,
              'numerical_contract':_numerical(
                  case_id,got_cls,got_rank,int(o[3]),int(o[4]))})
        first=per[0]['diagnostics'];case_reasons=[]
        for run in per:
            if not run['numerical_contract']['valid']:
                case_reasons.append(f"run_failed:{run['run_id']}")
        numerical={'expected':{'status':expect_cls,'rank':expect_rank},
          'actual':{'status':first['status'],'rank':first['rank']},
          'valid':not case_reasons,'reasons':case_reasons}
        row={'case_id':case_id,'inputs':[_input(case_id,A,b,x,input_seed)],
          'timings':[contract.timing_record(operation='router',
            source='solver-reported',warmups=0,repetitions=3,raw=raw)],
          'ratios':[],'runs':per,
          'diagnostics':{'status':first['status'],'rank':first['rank'],
            'rank_lo':first['rank_lo'],'rank_hi':first['rank_hi'],
            'router_relres':max((z['diagnostics']['router_relres'] for z in per
              if z['diagnostics']['router_relres'] is not None),default=None),
            'router_berr':max((z['diagnostics']['router_berr'] for z in per
              if z['diagnostics']['router_berr'] is not None),default=None)},
          'numerical_contract':numerical,
          'observations':{'timing_range':'not-evaluated'}}
        rows.append(row)
        print('STRUCT',name,'ok',not case_reasons,'ms',
              round(float(np.median(raw)*1e3),3),flush=True)
        del A,b,x
    return _section('structural',rows,{'routing_seeds_per_instance':3,
      'check_count':3*len(rows),'hard_failure_count':len(wrong),
      'reported_hard_failure_count':len(wrong),'failures':wrong,
      'max_consistent_relres':max(residuals) if residuals else None,
      'median_router_seconds':float(np.median(times))})


def lapack_gelsy(L,A,b,x):
    contract.ensure_abi_arrays(A,b,x)
    out=np.zeros(7,np.float64);L.bsolve_lapack_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],ptr(out));return out

def end2end_seconds(fn,warm=2,reps=7):
    for _ in range(warm):fn()
    t=[];last=None
    for _ in range(reps):
        q=time.perf_counter_ns();last=fn();t.append((time.perf_counter_ns()-q)*1e-9)
    return float(np.median(t)),last,t

def run_lapack_context(L,omp,*,candidate=False):
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
        case_id=f'lapack.{name}';A,b,x=maker()
        seed=contract.CANONICAL_CASES_BY_ID[case_id]['input_seeds'][0]
        rt,ro,rraw,runs=med_router(
            L,A,b,x,case_id=case_id,generator_seed=seed,omp=omp,warm=2,
            reps=7,warmup_seeds=[47001]*2,source='perf_counter_ns',
            candidate=candidate)
        lt,lo,lraw=end2end_seconds(lambda:lapack_gelsy(L,A,b,x),2,7)
        diag,numerical=_aggregate_runs(case_id,runs);diag['dgelsy']={
          'status':decode_status(lo[0]),'rank':int(lo[1]),
          'relres':None if not np.isfinite(lo[5]) else float(lo[5])}
        row={'case_id':case_id,'inputs':[_input(case_id,A,b,x,seed)],
          'timings':[
            contract.timing_record(operation='router',source='perf_counter_ns',
              warmups=2,repetitions=7,raw=rraw,unit='s'),
            contract.timing_record(operation='dgelsy',source='perf_counter_ns',
              warmups=2,repetitions=7,raw=lraw,unit='s')],
          'ratios':[_ratio(case_id,lt,rt)],'runs':runs,'diagnostics':diag,
          'numerical_contract':numerical,
          'observations':{'timing_range':'not-evaluated'}}
        rows.append(row);print('LAPACK',row,flush=True);del A,b,x
    ratios=[row['ratios'][0]['value'] for row in rows]
    return _section('lapack',rows,{'ratio_name':'dgelsy_over_router',
      'ratio_count':len(ratios),'ratio_geomean':float(np.exp(np.mean(np.log(ratios)))),
      'ratio_median':float(np.median(ratios))})


def source_state():
    def git(*args):
        return subprocess.check_output(['git','-C',str(ROOT),*args],
                                       text=True).strip()
    return {'git_sha':git('rev-parse','HEAD'),
            'git_tree_sha':git('rev-parse','HEAD^{tree}'),
            'git_dirty':bool(git('status','--porcelain=v1','--untracked-files=normal'))}

def _cpu_model():
    try:
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.lower().startswith(('model name','hardware')):
                return line.split(':',1)[-1].strip()
    except OSError:
        pass
    return platform.processor() or 'unknown'

def _physical_cores():
    try:
        rows=subprocess.check_output(['lscpu','-p=CORE,SOCKET'],text=True)
        return len({line for line in rows.splitlines() if line and not line.startswith('#')})
    except Exception:
        return os.cpu_count()

def machine_info():
    try: ram=int(os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES'))
    except (ValueError,OSError,AttributeError): ram=0
    return {'cpu_model':_cpu_model(),'physical_cores':_physical_cores(),
            'logical_cores':os.cpu_count(),'ram_bytes':ram,
            'os':platform.system(),'kernel':platform.release()}

def software_info():
    names=('numpy','scipy','scikit-learn','threadpoolctl','mpmath','joblib',
           'cloudpickle','narwhals')
    versions={name:importlib.metadata.version(name) for name in names}
    return {'python':platform.python_version(),**versions}

def runtime_info(build_evidence):
    pools=contract.partition_threadpools(threadpool_info())
    return {'loaded_router':{
              'basename':contract.ROUTER_BASENAME,
              'sha256':build_evidence['router_sha256']},
            **pools,
            'thread_controls':{name:os.environ.get(name) for name in (
              'OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS',
              'VECLIB_MAXIMUM_THREADS')},
            'openmp_schedule':[1,2,4]}

def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')

def _identity(path):
    path=Path(path)
    return {'path':path.relative_to(ROOT).as_posix(),
            'sha256':contract.sha256_file(path)}

def result_document(sections):
    valid=all(case['numerical_contract']['valid']
              for section in sections for case in section['cases'])
    reasons=[] if valid else ['one_or_more_case_contracts_failed']
    return {'schema_version':contract.RESULT_SCHEMA_VERSION,
            'protocol_id':contract.PROTOCOL_ID,
            'protocol_signature':contract.PROTOCOL_SIGNATURE,
            'sections':sections,
            'numerical_contract':{'valid':valid,'reasons':reasons}}

def numerical_exit_code(result):
    numerical=result.get('numerical_contract',{})
    return 0 if numerical.get('valid') is True and not numerical.get('reasons') else 1

def _metadata(*,args,result,before,after,build_evidence,runtime,started,
              ended,duration):
    result_bytes=contract.canonical_json_bytes(result)
    return {'schema_version':contract.METADATA_SCHEMA_VERSION,
      'scope':'reference-machine-numerical-evidence',
      'reference_machine_id':args.reference_machine,
      'result':{'filename':Path(args.out).name,
        'sha256':__import__('hashlib').sha256(result_bytes).hexdigest(),
        'schema_version':contract.RESULT_SCHEMA_VERSION,
        'protocol_id':contract.PROTOCOL_ID,
        'protocol_signature':contract.PROTOCOL_SIGNATURE},
      'source':{'before':before,'after':after},
      'generator':_identity(ROOT/'experiments/rerun_numerical_suite.py'),
      'dependency_locks':[_identity(ROOT/'requirements-numerical-suite.txt'),
                          _identity(ROOT/'requirements-ci.txt')],
      'command':{'executable_basename':Path(sys.executable).name,
                 'argv':['experiments/rerun_numerical_suite.py',*sys.argv[1:]]},
      'run':{'started_utc':started,'ended_utc':ended,
             'duration_seconds':float(duration)},
      'build':contract.sanitized_build_evidence(build_evidence),
      'runtime':runtime,'machine':machine_info(),'software':software_info(),
      'optional_observations':{},
      'evidence_eligibility':{'eligible':False,'reasons':['pending_validation']}}

def _atomic_json(path,document):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    payload=contract.canonical_json_bytes(document)
    descriptor,name=__import__('tempfile').mkstemp(prefix=f'.{path.name}.tmp.',
                                                  dir=path.parent)
    temporary=Path(name)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(payload);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        try: temporary.unlink()
        except FileNotFoundError: pass

def parse_cli(argv=None):
    canonical=','.join(name for name,_ in contract.CANONICAL_SECTIONS)
    ap=argparse.ArgumentParser()
    ap.add_argument('--omp',type=int,default=4)
    ap.add_argument('--out',default=str(ROOT/'results'/'numerical_rerun.json'))
    ap.add_argument('--sections',default='standard,rank,guard,scaling')
    ap.add_argument('--reference-machine')
    ap.add_argument('--metadata-out')
    ap.add_argument('--checksum-out')
    ap.add_argument('--candidate',action='store_true')
    args=ap.parse_args(argv)
    try: args.section_order=contract.parse_sections(args.sections,candidate=args.candidate)
    except ValueError as exc: ap.error(str(exc))
    if args.candidate:
        if not args.reference_machine: ap.error('--candidate requires --reference-machine')
        if args.omp!=4: ap.error('--candidate requires --omp=4')
        parent=Path(args.out).parent
        if Path(args.out).name=='numerical_rerun.json':
            args.out=str(parent/contract.RESULT_FILENAME)
        if args.metadata_out is None: args.metadata_out=str(parent/contract.METADATA_FILENAME)
        if args.checksum_out is None: args.checksum_out=str(parent/contract.CHECKSUM_FILENAME)
        names=(Path(args.out).name,Path(args.metadata_out).name,
               Path(args.checksum_out).name)
        if names!=(contract.RESULT_FILENAME,contract.METADATA_FILENAME,
                  contract.CHECKSUM_FILENAME):
            ap.error('--candidate outputs require canonical basenames')
        if args.sections!=canonical:
            ap.error('--candidate requires canonical section spelling and order')
    elif args.checksum_out:
        ap.error('diagnostic runs cannot produce a candidate checksum')
    return args

def _reverify(build_evidence,after):
    repeated=contract.verify_build_manifest(
      router_path=build_evidence['router_path'],
      manifest_path=build_evidence['manifest_path'],
      build_script_path=ROOT/'build.sh',source_state=after)
    if not repeated['verified'] or repeated['router_sha256']!=build_evidence['router_sha256'] \
            or repeated['manifest_sha256']!=build_evidence['manifest_sha256']:
        raise RuntimeError('source, router, or manifest changed during the run')
    repeated['router_path']=build_evidence['router_path']
    repeated['manifest_path']=build_evidence['manifest_path']
    return repeated

def main(argv=None,*,hooks=None):
    hooks={} if hooks is None else dict(hooks)
    source_state_fn=hooks.get('source_state',source_state)
    load_fn=hooks.get('load',load)
    runtime_info_fn=hooks.get('runtime_info',runtime_info)
    reverify_fn=hooks.get('reverify',_reverify)
    metadata_fn=hooks.get('metadata',_metadata)
    publish_fn=hooks.get('publish',contract.publish_package_atomic)
    atomic_json_fn=hooks.get('atomic_json',_atomic_json)
    utc_now_fn=hooks.get('utc_now',_utc_now)
    monotonic_fn=hooks.get('monotonic',time.monotonic)
    blas_context=hooks.get(
        'blas_context',lambda:threadpool_limits(limits=1,user_api='blas'))
    args=parse_cli(argv);before=source_state_fn();started=utc_now_fn();clock=monotonic_fn()
    if args.candidate and (before['git_dirty'] or len(before['git_sha'])!=40 or
                           len(before['git_tree_sha'])!=40):
        raise RuntimeError('candidate source preflight is not clean and complete')
    L,build_evidence=load_fn(before)
    functions={'standard':lambda:run_standard(L,args.omp,candidate=args.candidate),
      'rank':lambda:run_rank_transition(L,args.omp,candidate=args.candidate),
      'guard':lambda:run_guard_timing(L,args.omp,candidate=args.candidate),
      'scaling':lambda:run_scaling(L,candidate=args.candidate),
      'structural':lambda:run_structural(L,args.omp,candidate=args.candidate),
      'lapack':lambda:run_lapack_context(L,args.omp,candidate=args.candidate)}
    with blas_context():
        runtime=runtime_info_fn(build_evidence)
        if 'execute_sections' in hooks:
            sections=hooks['execute_sections'](L,args)
        else:
            sections=[functions[name]() for name in args.section_order]
        runtime=runtime_info_fn(build_evidence)
    result=result_document(sections);after=source_state_fn()
    build_evidence=reverify_fn(build_evidence,after)
    with blas_context():
        runtime=runtime_info_fn(build_evidence)
    ended=utc_now_fn()
    metadata=metadata_fn(args=args,result=result,before=before,after=after,
      build_evidence=build_evidence,runtime=runtime,started=started,ended=ended,
      duration=monotonic_fn()-clock)
    verdict=contract.evaluate_eligibility(result=result,metadata=metadata,
      candidate=args.candidate,omp=args.omp)
    metadata['evidence_eligibility']=verdict
    if args.candidate:
        final=contract.evaluate_eligibility(result=result,metadata=metadata,
          candidate=True,omp=args.omp)
        if not final['eligible']:
            raise RuntimeError('candidate evidence is ineligible: '+','.join(final['reasons']))
        publish_fn(result=result,metadata=metadata,
          result_path=args.out,metadata_path=args.metadata_out,
          checksum_path=args.checksum_out)
    else:
        atomic_json_fn(args.out,result)
        if args.metadata_out: atomic_json_fn(args.metadata_out,metadata)
    print('WROTE',args.out)
    return numerical_exit_code(result)

if __name__=='__main__': raise SystemExit(main())
