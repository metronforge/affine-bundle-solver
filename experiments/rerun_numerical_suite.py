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
from threadpoolctl import ThreadpoolController, threadpool_limits, threadpool_info

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from experiments import numerical_suite_contract as contract

DP=ctypes.POINTER(ctypes.c_double)
STATUS_CODES={1:'unique',2:'infinite',3:'inconsistent',4:'fail',5:'undecidable'}
CERTAINTY_CODES={1:'deterministic',2:'randomised',3:'none'}
ROUTER_OUTPUT_INDICES={
    'status':0,'certainty':1,'rank':2,'rank_lo':3,'rank_hi':4,
    'relres':5,'relx':6,'seconds':7,'fallback':8,'cls':9,'berr':10}
ABS_QUALITY_THRESHOLD=1e-14

def _exact_integer(value,name,*,allowed=None,minimum=None):
    if isinstance(value,(bool,np.bool_)) or not isinstance(
            value,(int,float,np.integer,np.floating)):
        raise ValueError(f'{name} must be an exact integer')
    try:value_float=float(value)
    except (TypeError,ValueError) as exc:
        raise ValueError(f'{name} must be an exact integer') from exc
    if not math.isfinite(value_float) or not value_float.is_integer():
        raise ValueError(f'{name} must be an exact finite integer')
    decoded=int(value_float)
    if minimum is not None and decoded<minimum:
        raise ValueError(f'{name} is below its minimum')
    if allowed is not None and decoded not in allowed:
        raise ValueError(f'unknown {name} {decoded}')
    return decoded

def decode_status(value):
    code=_exact_integer(value,'router status',allowed=STATUS_CODES)
    return STATUS_CODES[code]

def _decode_optional_nonnegative(value,name,*,unavailable):
    value=float(value)
    if math.isnan(value):
        if unavailable:return None
        raise ValueError(f'{name} is unexpectedly unavailable')
    if not math.isfinite(value) or value<0:
        raise ValueError(f'{name} must be finite and nonnegative')
    if unavailable:
        raise ValueError(f'{name} must use documented NaN when unavailable')
    return value

def _decode_positive(value,name):
    value=float(value)
    if not math.isfinite(value) or value<=0:
        raise ValueError(f'{name} must be positive and finite')
    return value

def decode_router_output(out):
    if len(out)!=11:raise ValueError('router output must contain 11 values')
    status_code=_exact_integer(out[0],'router status',allowed=STATUS_CODES)
    certainty_code=_exact_integer(
        out[1],'router certainty',allowed=CERTAINTY_CODES)
    rank=_exact_integer(out[2],'router rank',minimum=0)
    rank_lo=_exact_integer(out[3],'router rank_lo',minimum=0)
    rank_hi=_exact_integer(out[4],'router rank_hi',minimum=0)
    if not rank_lo<=rank<=rank_hi:
        raise ValueError('router rank is outside its interval')
    fallback_code=_exact_integer(out[8],'router fallback',allowed=(0,1))
    raw_class=_exact_integer(out[9],'router raw class',allowed=STATUS_CODES)
    if raw_class!=status_code:
        raise ValueError('router status and raw class disagree')
    status=STATUS_CODES[status_code];certainty=CERTAINTY_CODES[certainty_code]
    unavailable=status in ('fail','undecidable')
    if unavailable and certainty!='none':
        raise ValueError('FAIL and UNDECIDABLE require certainty NONE')
    if not unavailable and certainty=='none':
        raise ValueError('decided statuses cannot use certainty NONE')
    relres=_decode_optional_nonnegative(
        out[5],'router relative residual',unavailable=unavailable)
    relx=_decode_optional_nonnegative(
        out[6],'router relative reference error',
        unavailable=status in ('inconsistent','fail','undecidable'))
    berr_available=status=='unique' and certainty=='deterministic'
    berr=_decode_optional_nonnegative(
        out[10],'router BERR',unavailable=not berr_available)
    if berr is not None and berr>ABS_QUALITY_THRESHOLD:
        raise ValueError('deterministic UNIQUE BERR exceeds quality threshold')
    return {'status':status,'status_code':status_code,
      'certainty':certainty,'certainty_code':certainty_code,
      'rank':rank,'rank_lo':rank_lo,'rank_hi':rank_hi,
      'router_relres':relres,'router_relx':relx,
      'solver_seconds':_decode_positive(out[7],'router solver seconds'),
      'fallback':bool(fallback_code),'raw_class':raw_class,
      'router_berr':berr}

def decode_comparator_output(out):
    if len(out)!=7:raise ValueError('comparator output must contain 7 values')
    status_code=_exact_integer(out[0],'comparator status',allowed=STATUS_CODES)
    status=STATUS_CODES[status_code]
    rank=_exact_integer(out[1],'comparator rank',minimum=0)
    fallback=_exact_integer(out[2],'comparator fallback',allowed=(0,1))
    accepted=_exact_integer(out[3],'comparator accepted_random',allowed=(0,1))
    unavailable=status in ('fail','undecidable')
    return {'status':status,'status_code':status_code,'rank':rank,
      'fallback':bool(fallback),'accepted_random':bool(accepted),
      'solver_seconds':_decode_positive(out[4],'comparator solver seconds'),
      'relres':_decode_optional_nonnegative(
          out[5],'comparator relative residual',unavailable=unavailable),
      'relx':_decode_optional_nonnegative(
          out[6],'comparator relative reference error',
          unavailable=status in ('inconsistent','fail','undecidable'))}

def ptr(a): return a.ctypes.data_as(DP)

def load(source_state,lib_dir=None,cdll=ctypes.CDLL):
    return contract.resolve_and_load_router(
        root=ROOT,lib_dir=lib_dir or os.environ.get('ABS_LIB_DIR',ROOT),
        source_state=source_state,cdll=cdll)

def resolve_router_openmp_owner(L,*,dlopen=ctypes.CDLL):
    symbol=getattr(L,'omp_get_max_threads',None)
    if symbol is None:return None
    class DlInfo(ctypes.Structure):
        _fields_=[('filename',ctypes.c_char_p),('base',ctypes.c_void_p),
                  ('symbol_name',ctypes.c_char_p),('symbol',ctypes.c_void_p)]
    process=dlopen(None);dladdr=process.dladdr
    dladdr.argtypes=[ctypes.c_void_p,ctypes.POINTER(DlInfo)]
    dladdr.restype=ctypes.c_int;info=DlInfo()
    address=ctypes.cast(symbol,ctypes.c_void_p)
    if not address.value or dladdr(address,ctypes.byref(info))==0 or \
            not info.filename:return None
    return os.path.realpath(os.fsdecode(info.filename))

def _runtime_matches(pools,owner):
    if not owner:return []
    owner=os.path.realpath(owner)
    return [pool for pool in pools if pool.get('user_api')=='openmp' and
            isinstance(pool.get('filepath'),str) and
            os.path.realpath(pool['filepath'])==owner]

def _runtime_identity(pool):
    sanitized=contract.sanitize_threadpools(
        [pool],hash_libraries=False)[0]
    return {name:sanitized.get(name) for name in (
        'runtime_id','basename','user_api','internal_api','version')}

@contextlib.contextmanager
def openmp_runtime_context(L,requested,*,strict,
                           owner_resolver=resolve_router_openmp_owner,
                           controller_factory=ThreadpoolController):
    requested=_exact_integer(requested,'requested OpenMP threads',minimum=1)
    owner=owner_resolver(L);controller=controller_factory()
    matches=_runtime_matches(controller.info(),owner)
    reasons=[]
    if not owner:reasons.append('openmp_router_runtime_unidentified')
    elif not matches:reasons.append('openmp_router_runtime_pool_missing')
    elif len(matches)!=1:reasons.append('openmp_router_runtime_pool_ambiguous')
    if reasons:
        observation={'valid':False,'reasons':reasons,
          'requested_num_threads':requested,'observed_num_threads':None,
          'runtime_identity':None}
        if strict:raise RuntimeError(','.join(reasons))
        yield observation;return
    matched=matches[0]
    selected=controller.select(filepath=matched['filepath'])
    if len(selected.info())!=1:
        reason='openmp_router_runtime_pool_ambiguous'
        if strict:raise RuntimeError(reason)
        yield {'valid':False,'reasons':[reason],
          'requested_num_threads':requested,'observed_num_threads':None,
          'runtime_identity':None};return
    with selected.limit(limits=requested,user_api='openmp'):
        observed_matches=_runtime_matches(selected.info(),owner)
        observed=observed_matches[0].get('num_threads') \
            if len(observed_matches)==1 else None
        identity=_runtime_identity(observed_matches[0]) \
            if len(observed_matches)==1 else None
        if len(observed_matches)!=1:
            reasons.append('openmp_router_runtime_pool_missing')
        elif observed!=requested:
            reasons.append('openmp_requested_observed_mismatch')
        if identity is None or not all(
                isinstance(identity.get(name),str) and identity[name]
                for name in ('runtime_id','basename','user_api',
                             'internal_api','version')):
            reasons.append('openmp_runtime_identity_incomplete')
        observation={'valid':not reasons,'reasons':reasons,
          'requested_num_threads':requested,'observed_num_threads':observed,
          'runtime_identity':identity}
        if strict and reasons:raise RuntimeError(','.join(reasons))
        yield observation
        owner_after=owner_resolver(L)
        after_matches=_runtime_matches(controller_factory().info(),owner_after)
        after_identity=_runtime_identity(after_matches[0]) \
            if len(after_matches)==1 else None
        if os.path.realpath(owner_after or '')!=os.path.realpath(owner) or \
                len(after_matches)!=1 or after_identity!=identity:
            reasons.append('openmp_router_runtime_changed')
        elif after_matches[0].get('num_threads')!=requested:
            reasons.append('openmp_requested_observed_mismatch')
        observation['valid']=not reasons
        if strict and reasons:raise RuntimeError(','.join(dict.fromkeys(reasons)))

def router(L,A,b,x,seed=777):
    contract.ensure_abi_arrays(A,b,x)
    out=np.zeros(11,np.float64)
    L.bsolve_router_meta_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],
                             1,2,2,int(seed),0,ptr(out))
    return decode_router_output(out)

def seq(L,A,b,x):
    contract.ensure_abi_arrays(A,b,x)
    out=np.zeros(7,np.float64)
    L.bsolve_seq_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],ptr(out))
    return decode_comparator_output(out)

def med_router(L,A,b,x,*,case_id,generator_seed,omp=4,warm=4,reps=11,
               warmup_seeds=(),source='solver-reported',candidate=False,
               runtime_context=openmp_runtime_context,
               clock_ns=time.perf_counter_ns):
    spec=contract.CANONICAL_CASES_BY_ID[case_id]
    run_contract=spec['run_contract']
    warmup_seeds=list(warmup_seeds)
    if warmup_seeds!=run_contract['warmup_routing_seeds'] or \
            len(warmup_seeds)!=warm or reps!=len(run_contract['routing_seeds']):
        raise ValueError(f'configured run shape differs from protocol: {case_id}')
    values=[];last=None;captured=[]
    with runtime_context(L,omp,strict=candidate) as observation:
      for routing_seed in warmup_seeds:router(L,A,b,x,routing_seed)
      for repetition_index,routing_seed in enumerate(run_contract['routing_seeds']):
        started=clock_ns();last=router(L,A,b,x,routing_seed)
        wall_seconds=(clock_ns()-started)*1e-9
        duration=last['solver_seconds'] if source=='solver-reported' else wall_seconds
        values.append(duration);captured.append((repetition_index,routing_seed,
                                                 duration,last))
    runs=[]
    for repetition_index,routing_seed,duration,diagnostics in captured:
        numerical=_numerical(case_id,diagnostics['status'],diagnostics['rank'],
                             diagnostics['rank_lo'],diagnostics['rank_hi'])
        if not observation['valid']:
            numerical['valid']=False
            numerical['reasons'].extend(observation['reasons'])
        runs.append({
          'run_id':run_contract['run_id_format'].format(
              case_id=case_id,repetition_index=repetition_index),
          'case_id':case_id,'generator_seed':int(generator_seed),
          'routing_seed':int(routing_seed),'repetition_index':repetition_index,
          'requested_omp_threads':int(omp),
          'observed_omp_threads':observation['observed_num_threads'],
          'openmp_runtime_identity':observation['runtime_identity'],
          'duration':{'value':duration,'unit':'s'},
          'diagnostics':dict(diagnostics),'numerical_contract':numerical})
    return float(np.median(values)),last,values,runs

def _comparator_numerical(case_id,diagnostics):
    spec=contract.CANONICAL_CASES_BY_ID[case_id]
    expected={'status':spec['expected_status'],'rank':spec['expected_rank']}
    actual={'status':diagnostics['status'],'rank':diagnostics['rank']}
    reasons=[]
    if actual['status']!=expected['status']:reasons.append('status_mismatch')
    if actual['rank']!=expected['rank']:reasons.append('rank_mismatch')
    return {'expected':expected,'actual':actual,'valid':not reasons,
            'reasons':reasons}

def med_seq(L,A,b,x,*,case_id,warm=2,reps=7):
    comparator=contract.CANONICAL_CASES_BY_ID[case_id][
        'comparator_run_contracts'][0]
    for _ in range(warm): seq(L,A,b,x)
    vals=[];last=None;runs=[]
    for repetition_index in range(reps):
        last=seq(L,A,b,x);duration=last['solver_seconds'];vals.append(duration)
        runs.append({'run_id':comparator['run_id_format'].format(
          case_id=case_id,repetition_index=repetition_index),
          'case_id':case_id,'operation':'sequential_reference',
          'repetition_index':repetition_index,
          'duration':{'value':duration,'unit':'s'},'diagnostics':dict(last),
          'numerical_contract':_comparator_numerical(case_id,last)})
    return float(np.median(vals)),last,vals,runs

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
    definitions=(
      ('random64',make_random,(32768,64,64)),
      ('grouped64',make_grouped,(65536,64,64)),
      ('rankdef64',make_random,(32768,64,56)),
      ('inconsistent64',make_grouped,(32768,64,64,True)),
      ('digits',make_digits,()),
      ('random128',make_random,(32768,128,128)),
      ('grouped256',make_grouped,(32768,256,256)),
      ('rankdef256',make_random,(16384,256,240)),
      ('random512',make_random,(4096,512,512)))
    for name,maker,args in definitions:
        case_id=f'standard.{name}'
        seed=contract.CANONICAL_CASES_BY_ID[case_id]['input_seeds'][0]
        if name=='inconsistent64':
            arrays=maker(args[0],args[1],args[2],seed,args[3])
        elif name.startswith('grouped'):
            arrays=maker(args[0],args[1],args[2],seed,False)
        elif name=='digits':arrays=maker(seed)
        else:arrays=maker(*args,seed)
        yield name,arrays,seed

def _input(case_id,A,b,x,seed):
    spec=contract.CANONICAL_CASES_BY_ID[case_id]
    return contract.describe_input(A,b,x,generator=spec['generator'],seed=seed)

def _diagnostics(o):
    if not isinstance(o,dict):raise ValueError('router output was not decoded')
    return dict(o)

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

def _aggregate_runs(case_id,runs,comparator_runs=()):
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
    comparator_failures=[run['run_id'] for run in comparator_runs
                         if not run['numerical_contract']['valid']]
    if comparator_failures:
        numerical['valid']=False
        numerical['reasons'].extend(
            f'comparator_run_failed:{run_id}' for run_id in comparator_failures)
    return diagnostics,numerical

def _section(section_id,cases,summary=None):
    output=dict(contract.CANONICAL_SECTIONS)[section_id]
    details={'case_count':len(cases)}
    if summary: details.update(summary)
    return {'section_id':section_id,'output_name':output,
            'cases':cases,'summary':details}

def run_standard(L,omp,*,candidate=False):
    rows=[]
    for name,(A,b,x),generator_seed in standard_cases():
        case_id=f'standard.{name}'
        tr,ro,traw,runs=med_router(
            L,A,b,x,case_id=case_id,generator_seed=generator_seed,omp=omp,
            warm=4,reps=11,warmup_seeds=range(777,781),candidate=candidate)
        ts,so,sraw,comparator_runs=med_seq(
            L,A,b,x,case_id=case_id,warm=2,reps=7)
        diag,numerical=_aggregate_runs(case_id,runs,comparator_runs)
        diag['sequential_reference']=dict(so)
        rr={'case_id':case_id,'inputs':[_input(case_id,A,b,x,generator_seed)],
            'timings':[
              contract.timing_record(operation='router',source='solver-reported',
                warmups=4,repetitions=11,raw=traw),
              contract.timing_record(operation='sequential_reference',
                source='solver-reported',warmups=2,repetitions=7,raw=sraw)],
            'ratios':[_ratio(case_id,ts,tr)],'runs':runs,
            'comparator_runs':comparator_runs,
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
        with openmp_runtime_context(L,omp,strict=candidate) as observation:
          for repetition_index,(input_seed,routing_seed) in enumerate(zip(
                  run_contract['generator_seeds'],run_contract['routing_seeds'])):
            A,b,x=make_rank_transition(e,input_seed)
            inputs.append(_input(case_id,A,b,x,input_seed))
            diag=router(L,A,b,x,seed=routing_seed)
            key=diag['status'];states[key]=states.get(key,0)+1
            ranks[diag['rank']]=ranks.get(diag['rank'],0)+1
            rr=diag['router_relres']
            if rr is not None:residuals.append(rr)
            intervals.append([diag['rank_lo'],diag['rank_hi']])
            raw.append(diag['solver_seconds'])
            run_numerical=_numerical(
                case_id,key,diag['rank'],diag['rank_lo'],diag['rank_hi'])
            runs.append({'case_id':case_id,
              'run_id':run_contract['run_id_format'].format(
                  case_id=case_id,repetition_index=repetition_index),
              'generator_seed':input_seed,'routing_seed':routing_seed,
              'repetition_index':repetition_index,
              'requested_omp_threads':omp,
              'observed_omp_threads':observation['observed_num_threads'],
              'openmp_runtime_identity':observation['runtime_identity'],
              'duration':{'value':diag['solver_seconds'],'unit':'s'},
              'diagnostics':dict(diag),'numerical_contract':run_numerical})
        if not observation['valid']:
            for run in runs:
                run['numerical_contract']['valid']=False
                run['numerical_contract']['reasons'].extend(
                    observation['reasons'])
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
        case_diagnostics=dict(runs[-1]['diagnostics'])
        case_diagnostics.update({
          'router_relres':max(residuals) if residuals else None,
          'router_berr':max((run['diagnostics']['router_berr'] for run in runs
            if run['diagnostics']['router_berr'] is not None),default=None),
          'solver_seconds':float(np.median(raw)),
          'finite_residual_count':len(residuals),'states':states,
          'ranks':{str(k):v for k,v in ranks.items()},
          'rank_intervals':intervals})
        row={'case_id':case_id,'inputs':inputs,
             'timings':[contract.timing_record(operation='router',
               source='solver-reported',warmups=0,repetitions=20,raw=raw)],
             'ratios':[],'runs':runs,'comparator_runs':[],
             'diagnostics':case_diagnostics,
             'numerical_contract':numerical,
             'observations':{'timing_range':'not-evaluated','epsilon':e}}
        out.append(row); print('RANKTRANS',row,flush=True)
    return _section('rank',out)

def run_guard_timing(L,omp,*,candidate=False):
    cases=[(2000,64,63),(10000,64,63),(50000,64,63),(5000,96,95),(20000,96,95),(10000,64,32),(10000,64,1),(512,192,191)]
    out=[]
    for m,n,r in cases:
        case_id=f'guard.{m}x{n}.r{r}'
        seed=contract.CANONICAL_CASES_BY_ID[case_id]['input_seeds'][0]
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
             'ratios':[],'runs':runs,'comparator_runs':[],'diagnostics':diag,
             'numerical_contract':numerical,
             'observations':{'timing_range':'not-evaluated'}}
        out.append(row); print('GUARD',row,flush=True)
    return _section('guard',out)

def run_scaling(L,*,candidate=False):
    # Use three representative evidence-heavy cases; report router wall time relative to OMP=1.
    cases=[]
    for name,m,n,r,kind in [('grouped64',65536,64,64,'g'),('rankdef64',32768,64,56,'r'),('grouped256',32768,256,256,'g')]:
        seed=contract.CANONICAL_CASES_BY_ID[
            f'scaling.omp1.{name}']['input_seeds'][0]
        A,b,x=(make_grouped(m,n,r,seed,False) if kind=='g' else
               make_random(m,n,r,seed))
        cases.append((name,A,b,x,seed))
    rows=[];base={}
    for t in [1,2,4]:
        vals=[]
        for name,A,b,x,seed in cases:
            case_id=f'scaling.omp{t}.{name}'
            if seed!=contract.CANONICAL_CASES_BY_ID[case_id]['input_seeds'][0]:
                raise ValueError(f'scaling generator seed mismatch: {case_id}')
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
                 'ratios':[ratio],'runs':runs,'comparator_runs':[],
                 'diagnostics':diag,
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
    for case_id in contract.CANONICAL_CASE_IDS['structural']:
        spec=contract.CANONICAL_CASES_BY_ID[case_id]
        args=list(spec['generator_parameters']['args'])
        seed=spec['input_seeds'][0]
        if args[3]!=seed:
            raise ValueError(f'structural generator seed mismatch: {case_id}')
        if spec['generator']=='make_structured_rank':
            A,b,x=make_structured_rank(*args)
            if spec['generator_parameters'].get('contradiction'):
                b=b.copy();b[-1]+=0.25
        elif spec['generator']=='make_late_growth':
            A,b,x=make_late_growth(*args)
        else:
            raise ValueError(f'unknown structural generator: {spec["generator"]}')
        cases.append((case_id.removeprefix('structural.'),A,b,x,
                      spec['expected_status'],spec['expected_rank'],seed))
    assert len(cases)==44,len(cases)
    return cases

def run_structural(L,omp,*,candidate=False):
    rows=[];wrong=[];residuals=[];times=[]
    for ci,(name,A,b,x,expect_cls,expect_rank,input_seed) in enumerate(
            structural_cases()):
        case_id=f'structural.{name}';spec=contract.CANONICAL_CASES_BY_ID[case_id]
        per=[];raw=[]
        with openmp_runtime_context(L,omp,strict=candidate) as observation:
          for repetition_index,adjusted_seed in enumerate(
                  spec['run_contract']['routing_seeds']):
            diag=router(L,A,b,x,seed=adjusted_seed)
            got_cls=diag['status'];got_rank=diag['rank']
            rr=diag['router_relres']
            ok=(got_cls==expect_cls and got_rank==expect_rank)
            if not ok: wrong.append({'case_id':case_id,'seed':adjusted_seed,
              'expected':[expect_cls,expect_rank],
              'got':[got_cls,got_rank,diag['rank_lo'],diag['rank_hi']]})
            if rr is not None and expect_cls!='inconsistent':residuals.append(rr)
            raw.append(diag['solver_seconds']);times.append(diag['solver_seconds'])
            per.append({'case_id':case_id,
              'run_id':spec['run_contract']['run_id_format'].format(
                  case_id=case_id,repetition_index=repetition_index),
              'generator_seed':input_seed,'routing_seed':adjusted_seed,
              'repetition_index':repetition_index,
              'requested_omp_threads':omp,
              'observed_omp_threads':observation['observed_num_threads'],
              'openmp_runtime_identity':observation['runtime_identity'],
              'duration':{'value':diag['solver_seconds'],'unit':'s'},
              'diagnostics':dict(diag),
              'numerical_contract':_numerical(
                  case_id,got_cls,got_rank,diag['rank_lo'],diag['rank_hi'])})
        if not observation['valid']:
            for run in per:
                run['numerical_contract']['valid']=False
                run['numerical_contract']['reasons'].extend(
                    observation['reasons'])
        first=per[0]['diagnostics'];case_reasons=[]
        for run in per:
            if not run['numerical_contract']['valid']:
                case_reasons.append(f"run_failed:{run['run_id']}")
        numerical={'expected':{'status':expect_cls,'rank':expect_rank},
          'actual':{'status':first['status'],'rank':first['rank']},
          'valid':not case_reasons,'reasons':case_reasons}
        case_diagnostics=dict(first)
        case_diagnostics.update({
            'router_relres':max((z['diagnostics']['router_relres'] for z in per
              if z['diagnostics']['router_relres'] is not None),default=None),
            'router_berr':max((z['diagnostics']['router_berr'] for z in per
              if z['diagnostics']['router_berr'] is not None),default=None),
            'solver_seconds':float(np.median(raw))})
        row={'case_id':case_id,'inputs':[_input(case_id,A,b,x,input_seed)],
          'timings':[contract.timing_record(operation='router',
            source='solver-reported',warmups=0,repetitions=3,raw=raw)],
          'ratios':[],'runs':per,'comparator_runs':[],
          'diagnostics':case_diagnostics,
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
    out=np.zeros(7,np.float64);L.bsolve_lapack_api(ptr(A),ptr(b),ptr(x),A.shape[0],A.shape[1],ptr(out));return decode_comparator_output(out)

def end2end_seconds(fn,*,case_id,operation,warm=2,reps=7,
                     clock_ns=time.perf_counter_ns):
    comparator=next(item for item in contract.CANONICAL_CASES_BY_ID[
        case_id]['comparator_run_contracts'] if item['operation']==operation)
    if reps!=len(comparator['repetition_indices']):
        raise ValueError(f'comparator run shape differs from protocol: {case_id}')
    for _ in range(warm):fn()
    t=[];last=None;runs=[]
    for repetition_index in range(reps):
        q=clock_ns();last=fn();duration=(clock_ns()-q)*1e-9;t.append(duration)
        runs.append({'run_id':comparator['run_id_format'].format(
          case_id=case_id,repetition_index=repetition_index),
          'case_id':case_id,'operation':operation,
          'repetition_index':repetition_index,
          'duration':{'value':duration,'unit':'s'},'diagnostics':dict(last),
          'numerical_contract':_comparator_numerical(case_id,last)})
    return float(np.median(t)),last,t,runs

def run_lapack_context(L,omp,*,candidate=False):
    rows=[]
    # A representative subset spanning full rank, deficient rank, redundancy, and size.
    specs=[('random64',make_random,(32768,64,64)),
      ('grouped64',make_grouped,(65536,64,64)),
      ('rankdef64',make_random,(32768,64,56)),
      ('random128',make_random,(32768,128,128)),
      ('rankdef256',make_random,(16384,256,240)),
      ('random512',make_random,(4096,512,512))]
    for name,maker,maker_args in specs:
        case_id=f'lapack.{name}'
        seed=contract.CANONICAL_CASES_BY_ID[case_id]['input_seeds'][0]
        A,b,x=(maker(*maker_args,seed,False) if name.startswith('grouped')
               else maker(*maker_args,seed))
        rt,ro,rraw,runs=med_router(
            L,A,b,x,case_id=case_id,generator_seed=seed,omp=omp,warm=2,
            reps=7,warmup_seeds=[47001]*2,source='perf_counter_ns',
            candidate=candidate)
        lt,lo,lraw,comparator_runs=end2end_seconds(
            lambda:lapack_gelsy(L,A,b,x),case_id=case_id,
            operation='dgelsy',warm=2,reps=7)
        diag,numerical=_aggregate_runs(case_id,runs,comparator_runs)
        diag['dgelsy']=dict(lo)
        row={'case_id':case_id,'inputs':[_input(case_id,A,b,x,seed)],
          'timings':[
            contract.timing_record(operation='router',source='perf_counter_ns',
              warmups=2,repetitions=7,raw=rraw,unit='s'),
            contract.timing_record(operation='dgelsy',source='perf_counter_ns',
              warmups=2,repetitions=7,raw=lraw,unit='s')],
          'ratios':[_ratio(case_id,lt,rt)],'runs':runs,
          'comparator_runs':comparator_runs,'diagnostics':diag,
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
            'evidence_counts':{
              'router_runs':sum(len(case.get('runs',[])) for section in sections
                for case in section['cases']),
              'sequential_reference_runs':sum(
                run.get('operation')=='sequential_reference'
                for section in sections for case in section['cases']
                for run in case.get('comparator_runs',[])),
              'dgelsy_runs':sum(run.get('operation')=='dgelsy'
                for section in sections for case in section['cases']
                for run in case.get('comparator_runs',[])),
              'ratios':sum(len(case.get('ratios',[])) for section in sections
                for case in section['cases'])},
            'numerical_contract':{'valid':valid,'reasons':reasons}}

def _selected_openmp_identity(result):
    identities=[run.get('openmp_runtime_identity')
      for section in result.get('sections',[])
      for case in section.get('cases',[])
      for run in case.get('runs',[]) if isinstance(run,dict)]
    return identities[0] if identities and all(
        identity==identities[0] for identity in identities) else None

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
    runtime['selected_router_openmp_identity']=_selected_openmp_identity(result)
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
