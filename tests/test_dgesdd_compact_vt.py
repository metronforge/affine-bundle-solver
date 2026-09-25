"""Structural guards for the private compact-DGESDD core state.

These assertions deliberately protect the allocation/indexing contract in the
only private SVD state implementation.  They do not widen the public ABI.
"""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CORE = (ROOT / "src" / "bsolver_core.c").read_text()
SYMBOLS = (ROOT / "src" / "blas_symbols.h").read_text()


def require(pattern, text=CORE):
    assert re.search(pattern, text, re.S), pattern


require(r"extern void dgesdd_\(char\*,int\*,int\*,double\*,int\*,double\*,double\*,int\*,double\*,int\*,double\*,int\*,int\*,int\*\);")
require(r"#define dgesdd_\s+scipy_dgesdd_", SYMBOLS)
require(r"minmn=M<N\?M:N")
require(r"size_mul\(\(size_t\)minmn,\(size_t\)N,&vt_count\)")
require(r"VT=array_alloc\(vt_count,sizeof\(\*VT\)\)")
require(r"LDU=M,LDVT=minmn")
require(r"size_mul\(8u,\(size_t\)minmn,&iwork_count\)")
require(r"iwork=array_alloc\(iwork_count,sizeof\(\*iwork\)\)")
require(r"dgesdd_\(&job,&M,&N,Ac,&LDA,sv,U,&LDU,VT,&LDVT,&wq,&lw,iwork,&info\)")
require(r"VT\[l\+\(size_t\)j\*LDVT\]")
assert len(re.findall(r"VT\[l\+\(size_t\)j\*LDVT\]", CORE)) == 2
require(r"if\(!Ac\|\|!sv\|\|!U\|\|!VT\|\|!iwork\)")
require(r"if\(info\)\{free\(Ac\);free\(sv\);free\(U\);free\(VT\);free\(work\);free\(iwork\);return -1;\}")
require(r"if\(info\|\|!finite_bits\(wq\)\|\|wq<1\.0\|\|wq>\(double\)INT_MAX\)")

print("PASS: compact DGESDD private state contract")
