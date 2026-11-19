"""Inspect independent rank/quality evidence and compare public certificate radii."""
import argparse
import json
import time
from pathlib import Path
from bench import api, inputs, np
from split_api_qualification import oracle_quality

def observe(lib, name, cache):
    A,b = inputs(name,cache)
    p = api.default_policy(lib)
    rc,x,out = api.invoke_solve(lib,A,b,p)
    assert rc == 0
    start = time.perf_counter_ns()
    rc,check = api.invoke_candidate_check(lib,A,b,x,p)
    check_ms = (time.perf_counter_ns()-start)/1e6
    assert rc == 0
    start = time.perf_counter_ns()
    rc,c = api.invoke_candidate_certification(lib,A,b,x)
    cert_ms = (time.perf_counter_ns()-start)/1e6
    assert rc == 0
    max_resid, berr = oracle_quality(A,b,x)
    assert check.mixed_backward_error_up >= berr
    assert check.max_abs_residual_up >= max_resid
    s = np.linalg.svd(A,compute_uv=False)
    return dict(status=out.operational_status, certainty=out.operational_certainty,
                rank=list(out.router_meta)[2:5], guards=list(out.formation_guard_counters),
                check=check.verdict, backward_upper=check.mixed_backward_error_up,
                backward_oracle=berr, sv_ratio=s[-1]/s[0], mask=c.nearby_status_mask,
                radii=[float(getattr(c,k)).hex() for k in ("eta_unique","eta_infinite","eta_inconsistent")],
                check_ms=check_ms,certify_ms=cert_ms)

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("library",type=Path)
    p.add_argument("cases",nargs="+")
    p.add_argument("--cache",type=Path,default=Path("/tmp/ralph-inputs"))
    args=p.parse_args()
    lib=api.load_library(args.library)
    print(json.dumps({n:observe(lib,n,args.cache) for n in args.cases},indent=2))
