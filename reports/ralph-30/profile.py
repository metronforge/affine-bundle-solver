"""Instrument only a disposable worktree, then measure one warmed public call."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

from bench import inputs, api, CASES

FUNCTIONS = {
    "bsolver_core.c": ["bs_copy","sketch_remainder"],
    "bsolver.c": ["core_qr_state","certified_proof_rank_lo","source_qrcp_policy",
                  "compat_scan_fused","bs_insert_certified","bs_check_certified",
                  "try_secant_tail","solve_blockprefix_qr","try_square_lu_unique",
                  "proof_rows_add_normalized","solve_router_raw"],
    "operational_policy.inc": ["bsolve_router_policy_api"],
    "formation_guard.c": ["fg_qr_rank_certifies"],
    "certified_api.c": ["least_squares_x","bsolve"],
}
HEADER = r"""
#ifndef RALPH_PROFILE
#define RALPH_PROFILE
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
typedef struct { const char *name; double start; int active; } RalphSpan;
static double ralph_now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec+t.tv_nsec*1e-9;
}
static void ralph_finish(RalphSpan *s) {
    if(s->active) fprintf(stderr,"SPAN %s %.9f\n",s->name,ralph_now()-s->start);
}
#define RALPH_SPAN RalphSpan span __attribute__((cleanup(ralph_finish))) = {__func__, ralph_now(), getenv("RALPH_TRACE")!=NULL}
#endif
"""
def instrument(root):
    for name, funcs in FUNCTIONS.items():
        path = root / "src" / name
        src = path.read_text()
        for fn in funcs:
            pattern = r"(?m)^(?:static )?(?:int|void|Result)\s+" + fn + r"\s*\([^;{}]*\)\s*\{"
            matches = list(re.finditer(pattern, src))
            if len(matches) != 1:
                raise ValueError((name, fn, len(matches)))
            i = matches[0].end()
            src = src[:i] + "\n RALPH_SPAN;\n" + src[i:]
        if name == "bsolver.c":
            for anchor, label, args in [
                ("g_last_core_qr_rank=r;", "qr %d %d %d", "rows,n,r"),
                ("s->r++;return 1;", "growth %d", "s->r+1"),
            ]:
                src = src.replace(anchor,'if (getenv("RALPH_TRACE")) fprintf(stderr,"EVENT '+
                                  label+'\\n",'+args+');'+anchor,1)
        path.write_text(HEADER + src)
    subprocess.run(["./build.sh"], cwd=root, check=True)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--instrument", action="store_true")
    ap.add_argument("--case", choices=CASES)
    args = ap.parse_args()
    if args.instrument:
        instrument(args.root)
    if args.case:
        lib = api.load_library(args.root)
        A,b = inputs(args.case,Path("/tmp/ralph-inputs"))
        p = api.default_policy(lib)
        api.invoke_solve(lib,A,b,p)
        os.environ["RALPH_TRACE"] = "1"
        for trial in range(5):
            print("CALL",trial,file=sys.stderr,flush=True)
            rc,x,out = api.invoke_solve(lib,A,b,p)
            assert rc == 0
            print("GUARDS",*out.formation_guard_counters,file=sys.stderr)

