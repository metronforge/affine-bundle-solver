"""Run with count_calls.so preloaded; see README for compile command."""
import ctypes as C
import json
from pathlib import Path
import sys
from experiment import HERE, api, np

lib=api.load_library(Path(sys.argv[1]))
hooks=C.CDLL(None)
rows={}
for name in sys.argv[2:]:
    with np.load(HERE/"inputs"/(name+".npz")) as d:
        A,b,x=[d[k] for k in ("A","b","x")]
    out=api.CandidateCertificateResult()
    lib.bs_init_certificate_result(C.byref(out))
    dp=lambda v:v.ctypes.data_as(api.DP)
    args=(dp(A),dp(b),dp(x),*A.shape,C.byref(out))
    assert lib.bs_certify_candidate(*args)==0
    events=(C.c_uint64*3)()
    hooks.start_counts()
    rc=lib.bs_certify_candidate(*args)
    hooks.stop_counts(events)
    assert rc==0
    rows[name]=dict(zip(("fesetround","frexp","scalbn"),events))
print(json.dumps(rows,indent=2))
