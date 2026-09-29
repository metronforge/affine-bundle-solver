#!/usr/bin/env python3
"""Frozen builds and real-private-tail replay. No source copies or loop rewrites."""
import argparse
import ctypes as ct
import hashlib
import json
import os
from pathlib import Path
import random
import shlex
import subprocess
import time
import compat_scan_bench as common

ROOT=common.ROOT
STATS=('entries','serial_rows','blocks','block_rows','serial_updates','block_updates',
       'insertions','growths','scan_seconds','prefix_rank','prefix_rows','reserved')

def build(args):
    common.build(args)
    dest=Path(args.directory).resolve()
    freeze=json.loads((dest/'freeze.json').read_text())
    commands=freeze['compile_commands']
    router=next(c for c in commands if 'abs_router_obj.dir' in c['command'])
    extra=[]
    for name,diag in [('tail',False),('trace',True)]:
        cmd=shlex.split(router['command'])
        cmd[cmd.index('-o')+1]=str(dest/f'{name}.o')
        cmd[cmd.index('-c')+1]=str(ROOT/'experiments/tail_scan_probe.c')
        cmd += ['-I'+str(ROOT/'experiments'), '-fopt-info-vec-all='+str(dest/f'{name}-vectorization.txt')]
        if diag:cmd+=['-DABS_TAIL_DIAGNOSTICS']
        subprocess.run(cmd,cwd=dest,check=True)
        link=shlex.split((dest/'CMakeFiles/affine_bundle_solver.dir/link.txt').read_text())
        link=[str(dest/f'{name}.o') if x.endswith('abs_router_obj.dir/src/bsolver.c.o') else x for x in link]
        link[link.index('-o')+1]=str(dest/f'lib{name}.so')
        link+=['-Wl,-Bsymbolic']
        subprocess.run(link,cwd=dest,check=True)
        extra += [cmd,link]
    prod=dest/'CMakeFiles/abs_router_obj.dir/src/bsolver.c.o'
    # Reports on the production TU, plus its actual object disassembly.
    cmd=shlex.split(router['command'])
    cmd[cmd.index('-o')+1]=str(dest/'audit-router.o')
    cmd+=['-fopt-info-vec-all='+str(dest/'production-vectorization.txt')]
    subprocess.run(cmd,cwd=dest,check=True)
    assert common.sha(prod)==common.sha(dest/'audit-router.o')
    for obj,label in [(prod,'production'),(dest/'tail.o','replay'),(dest/'trace.o','trace')]:
        syms=common.run(['nm',str(obj)]).splitlines()
        for line in syms:
            sym=line.split()[-1]
            if sym.startswith('try_secant_tail') or sym=='abs_tail_replay':
                (dest/f'{label}-{sym}.asm').write_text(common.run(['objdump','-d','-Mintel','--disassemble='+sym,str(obj)])+'\n')
    freeze['diagnostic_commands']=extra
    freeze['binaries']={p.name:common.sha(p) for p in dest.glob('*.so')}
    freeze['router_object_sha256']=common.sha(prod)
    freeze['diagnostic_objects']={p.name:common.sha(p) for p in [dest/'tail.o',dest/'trace.o']}
    (dest/'freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')

def load(path):
    import numpy as np
    path=Path(path)
    freeze=json.loads((path/'freeze.json').read_text())
    for p,h in freeze['binaries'].items():assert common.sha(path/p)==h
    dp=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
    prod=ct.CDLL(str(path/'libaffine_bundle_solver.so'))
    trace=ct.CDLL(str(path/'libtrace.so'))
    replay=ct.CDLL(str(path/'libtail.so'))
    for lib in [prod,trace,replay]:
        lib.bsolve_router_api.argtypes=[dp,dp,ct.c_void_p]+[ct.c_int]*5+[ct.c_ulonglong,ct.c_int,dp]
        lib.bsolve_router_api.restype=None
    trace.abs_tail_reset.argtypes=[];trace.abs_tail_reset.restype=None
    trace.abs_tail_release.argtypes=[];trace.abs_tail_release.restype=None
    trace.abs_tail_stats.argtypes=[dp];trace.abs_tail_stats.restype=None
    trace.abs_tail_state.argtypes=[ct.POINTER(ct.c_int)];trace.abs_tail_state.restype=ct.c_void_p
    replay.abs_tail_replay.argtypes=[dp,dp,ct.c_int,ct.c_int,ct.c_int,ct.c_void_p,ct.c_ulonglong,dp]
    replay.abs_tail_replay.restype=None
    return prod,trace,replay,freeze

def make_case(m,n,kind,seed=20260929):
    import numpy as np
    rng=np.random.default_rng(seed+n+m)
    a=rng.standard_normal((m,n))
    if kind=='rankdef':a[:,-1]=0.0
    elif kind=='half':a[:,n//2:]=0.0
    elif kind=='growth':
        a[:,:]=0.0
        a[:,:n//2]=rng.standard_normal((m,n//2))
        a[m//2:,n//2]=rng.standard_normal(m-m//2)
    elif kind!='full':raise ValueError(kind)
    x=rng.standard_normal(n)
    b=np.ascontiguousarray(a@x)
    return a,b

def invoke(lib,a,b,out,seed=20260909):
    lib.bsolve_router_api(a,b,None,*a.shape,1,2,2,seed,0,out)

def semantic(out):return out[[0,1,2,3]].tolist()

def bench(args):
    for k in common.THREADS:
        expected=str(args.threads) if k=='OMP_NUM_THREADS' else '1'
        if os.environ.get(k)!=expected:raise SystemExit(f'Set {k}={expected}')
    import numpy as np
    os.sched_setaffinity(0,set(map(int,args.cpus.split(','))))
    libs={k:load(v) for k,v in (s.split('=',1) for s in args.variant)}
    result={'protocol':{'repeats':args.repeats,'warmups':3,'cpus':args.cpus,'threads':{k:os.environ[k] for k in common.THREADS},'seed':20260909,'timing':'separate uninstrumented replay and production router; telemetry separate'},'builds':{k:v[3] for k,v in libs.items()},'cases':[]}
    for spec in args.cases.split(','):
        kind,shape=spec.split(':');m,n=map(int,shape.split('x'))
        a,b=make_case(m,n,kind)
        case={'case':spec,'input_sha256':hashlib.sha256(a.tobytes()+b.tobytes()).hexdigest(),'trace':{},'results':{}}
        states={}
        for label,(prod,trace,replay,_) in libs.items():
            out=np.zeros(8);normal=np.zeros(8);stats=np.zeros(12)
            trace.abs_tail_reset();invoke(trace,a,b,out);trace.abs_tail_stats(stats)
            invoke(prod,a,b,normal)
            assert semantic(out)==semantic(normal),(spec,label,out,normal)
            assert np.array_equal(out[[5,6]],normal[[5,6]],equal_nan=True),(spec,label,'instrumentation diagnostic change',out,normal)
            p=ct.c_int();state=trace.abs_tail_state(ct.byref(p))
            # Only a current entry authorizes replay; a prior case may have saved state.
            states[label]=(p.value,state) if stats[0] else None
            case['trace'][label]=dict(zip(STATS,stats.tolist()))
            case['trace'][label]['output']=out.tolist()
        for mode in ['tail','router']:
            labels=[k for k in libs if mode=='router' or states[k]]
            times={k:[] for k in labels};outs={k:np.zeros(8) for k in labels};decisions={k:set() for k in labels}
            rng=random.Random(1234)
            for rep in range(args.repeats+3):
                order=labels.copy();rng.shuffle(order)
                for k in order:
                    prod,trace,replay,_=libs[k]
                    t=time.perf_counter()
                    if mode=='router':invoke(prod,a,b,outs[k])
                    else:
                        p,state=states[k];replay.abs_tail_replay(a,b,m,n,p,state,20260909,outs[k])
                    elapsed=time.perf_counter()-t
                    decisions[k].add(tuple(semantic(outs[k])))
                    if rep>=3:times[k].append(elapsed)
            case['results'][mode]={k:{**common.summary(times[k]),'output':outs[k].tolist(),'decisions':[list(v) for v in sorted(decisions[k])]} for k in labels}
        # Profiling invocations are separate from ALL benchmark intervals above.
        for k,(prod,trace,replay,_) in libs.items():
            phases=[];totals=[];out=np.zeros(8);stats=np.zeros(12)
            for rep in range(args.repeats):
                trace.abs_tail_reset();t=time.perf_counter();invoke(trace,a,b,out);totals.append(time.perf_counter()-t)
                trace.abs_tail_stats(stats);phases.append(stats[8])
            case['trace'][k]['phase']=common.summary(phases)
            case['trace'][k]['profile_router']=common.summary(totals)
            trace.abs_tail_release()
        result['cases'].append(case)
        Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
        print(spec,{k:case['trace'][k]['serial_rows']+case['trace'][k]['block_rows'] for k in libs},{mode:{k:round(v['median']*1e3,3) for k,v in rows.items()} for mode,rows in case['results'].items()},flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build');b.add_argument('directory');b.add_argument('--scalar',action='store_true');b.set_defaults(func=build)
    b=sub.add_parser('bench');b.add_argument('--variant',action='append',required=True);b.add_argument('--cases',default='rankdef:8192x192,rankdef:8192x193,rankdef:8192x256,rankdef:8192x512,half:16384x256,full:8192x192');b.add_argument('--repeats',type=int,default=21);b.add_argument('--threads',type=int,default=1);b.add_argument('--cpus',default='0');b.add_argument('--output',required=True);b.set_defaults(func=bench)
    args=p.parse_args();args.func(args)
if __name__=='__main__':main()
