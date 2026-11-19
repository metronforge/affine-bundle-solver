"""Summarize one stored block experiment, including correlated family uncertainty."""
import json
from pathlib import Path
import sys
import numpy as np
from bench import PRIMARY

def summarize(path, names):
    data = json.loads(Path(path).read_text())
    blocks = data["blocks"]
    rng = np.random.default_rng(42)
    indices = rng.integers(len(blocks), size=(4000, len(blocks)))
    ratios = []
    point = []
    for name in names:
        a,b = [np.array([np.median(row[k][name]["ms"]) for row in blocks])
               for k in ("base","new")]
        point.append(np.median(b)/np.median(a))
        ratios.append(np.median(b[indices],axis=1)/np.median(a[indices],axis=1))
    boot = np.exp(np.mean(np.log(ratios),axis=0))
    return np.exp(np.mean(np.log(point))),np.quantile(boot,[.025,.975])

if __name__ == "__main__":
    print(summarize(sys.argv[1],sys.argv[2:] or PRIMARY))
