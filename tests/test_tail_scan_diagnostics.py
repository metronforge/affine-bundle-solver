#!/usr/bin/env python3
"""Finite diagnostic-equivalence gate; no decision-equivalence claim for control."""
import argparse
import ctypes as ct
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
import numpy as np
from tail_scan_bench import load, make_case, invoke, semantic

p=argparse.ArgumentParser();p.add_argument('--normal',required=True);p.add_argument('--control',required=True);p.add_argument('--output',required=True);args=p.parse_args()
libs={k:load(v) for k,v in [('normal',args.normal),('control',args.control)]}
result={'instrumentation_cases':0,'instrumentation_decision_changes':[], 'instrumentation_diagnostic_changes':[], 'control_router_decision_changes':[], 'row_cases':0,'control_row_decision_changes':[],'control_row_diagnostic_changes':[], 'quality_decision_changes':'not separately probed: no arithmetic variant; tail row body has no quality gate'}
for n in [192,193,196,256]:
 for kind in ['rankdef','half','growth','full']:
  for scale in [1e-150,1.,1e150]:
   a,b=make_case(n+96,n,kind);a*=scale;b*=scale
   ident=f'{kind}/{n}/{scale}'
   outputs={}
   for label,(prod,trace,_,_,profile) in libs.items():
    plain=np.zeros(8);diag=np.zeros(8)
    trace.abs_tail_reset();invoke(prod,a,b,plain);invoke(trace,a,b,diag)
    prof=np.zeros(8);profile.abs_tail_reset();invoke(profile,a,b,prof)
    assert np.array_equal(plain[[0,1,2,3,5,6]],prof[[0,1,2,3,5,6]],equal_nan=True),(ident,label,'timer-only profile differs')
    profile.abs_tail_release()
    outputs[label]=plain
    result['instrumentation_cases']+=1
    if semantic(plain)!=semantic(diag):result['instrumentation_decision_changes'].append([ident,label,plain.tolist(),diag.tolist()])
    if not np.array_equal(plain[[5,6]],diag[[5,6]],equal_nan=True):result['instrumentation_diagnostic_changes'].append([ident,label,plain.tolist(),diag.tolist()])
    trace.abs_tail_release()
   if semantic(outputs['normal'])!=semantic(outputs['control']):result['control_router_decision_changes'].append([ident,outputs['normal'].tolist(),outputs['control'].tolist()])
for n in [1,2,3,4,7,32,64,188,191,192,193,194,195,196,255,256,257,511,512,513]:
 for shift in [0,1]:
  for scale in [0.,1e-200,1.,1e200]:
   for factor in [0.99,1.,1.01]:
    rng=np.random.default_rng(n+shift)
    storage=np.empty(8*n+shift);a=storage[shift:].reshape(8,n);a[:]=rng.standard_normal((8,n))*scale
    x=np.zeros(n);z=np.zeros(2*n)
    # Stable norm for extreme scales, input generation only.
    norm=np.sqrt(np.sum((a/scale)**2,axis=1))*scale if scale else np.zeros(8)
    b=np.ascontiguousarray(norm*(2e-10/(1-2e-10))*factor)
    for updates in [0,1]:
     out={k:np.zeros(8) for k in libs}
     for k,(_,_,replay,_,_) in libs.items():replay.abs_tail_rows(a,b,x,z,8,n,updates,20260909,out[k])
     ident=f'n={n}/shift={shift}/scale={scale}/factor={factor}/updates={updates}'
     result['row_cases']+=1
     if out['normal'][0]!=out['control'][0]:result['control_row_decision_changes'].append([ident,out['normal'].tolist(),out['control'].tolist()])
     if not np.array_equal(out['normal'][1:5],out['control'][1:5],equal_nan=True):result['control_row_diagnostic_changes'].append([ident,out['normal'].tolist(),out['control'].tolist()])
Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
print({k:len(v) if isinstance(v,list) else v for k,v in result.items()})
assert not result['instrumentation_decision_changes']
assert not result['instrumentation_diagnostic_changes']
