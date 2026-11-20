"""Replay the inconsistent certificate actually chosen by the public API."""
import ctypes as C
import json
import os
from pathlib import Path
import sys
from experiment import api, np, HERE

root=Path(sys.argv[1]).resolve()
os.environ["ABS_LIB_DIR"]=str(root)
from pbt_certificate_equivariance import shadow_inconsistent, mp
lib=api.load_library(root)
real=C.CDLL(str(root/"libstatus_verifier.so")).bs_verify_inconsistent
hook=C.CDLL(None)
hook.capture_begin.argtypes=[api.DP,C.c_int,C.c_void_p]
hook.capture_end.argtypes=[C.POINTER(C.c_int),api.DP]
mp.mp.dps=100
out={}
for name in sys.argv[2:]:
    with np.load(HERE/"inputs"/(name+".npz")) as d:
        A,b,x=[d[k] for k in ("A","b","x")]
    y=np.empty(len(b))
    hook.capture_begin(y.ctypes.data_as(api.DP),len(y),C.cast(real,C.c_void_p))
    rc,cert=api.invoke_candidate_certification(lib,A,b,x)
    counts,eta=(C.c_int*2)(),C.c_double()
    pivot=hook.capture_end(counts,C.byref(eta))
    assert rc==0 and pivot>=0 and cert.nearby_status_mask & 4
    assert eta.value.hex()==cert.eta_inconsistent.hex()
    oracle=shadow_inconsistent(A,b,(y,pivot))
    assert mp.mpf(eta.value)>=oracle
    signed=mp.fsum(mp.mpf(float(v))*float(w) for v,w in zip(y,b))
    assert signed!=0
    out[name]=dict(attempts=counts[0],accepted=counts[1],pivot=pivot,
                   eta=eta.value.hex(),oracle=str(oracle),ratio=float(mp.mpf(eta.value)/oracle))
print(json.dumps(out,indent=2))
