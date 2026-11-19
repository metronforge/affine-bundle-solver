"""Check the linked SciPy LP64 DGELSY workspace-query convention."""
import ctypes as c
from pathlib import Path
import numpy as np
import scipy
path = next((Path(scipy.__file__).resolve().parent.parent/"scipy.libs").glob("libscipy_openblas*.so"))
gelsy = c.CDLL(str(path)).scipy_dgelsy_
for m,n in [(96,512),(192,192),(8000,32)]:
    observed = []
    for fill in (0,1,float("nan")):
        a = np.full((m,n),fill,dtype="d",order="F")
        b = np.full(max(m,n),fill,dtype="d")
        piv = np.zeros(n,dtype="i")
        M,N,K,lda,ldb,rank,lwork,info = map(c.c_int,(m,n,1,m,len(b),0,-1,0))
        work, cond = c.c_double(), c.c_double(1e-12)
        ref = c.byref
        gelsy(ref(M),ref(N),ref(K),a.ctypes.data_as(c.c_void_p),ref(lda),
              b.ctypes.data_as(c.c_void_p),ref(ldb),piv.ctypes.data_as(c.c_void_p),
              ref(cond),ref(rank),ref(work),ref(lwork),ref(info))
        assert info.value == 0
        observed.append(work.value)
    print(m,n,observed)
    assert len(set(observed)) == 1
