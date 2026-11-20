"""Execute the reference semantics and observe the shadow sample on a built main."""
import json
import runpy
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

root = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(root / 'tests'), str(root / 'experiments')]
import pbt_certificate_equivariance as cert
import pbt_equivalence_orbits as orbit
import rerun_applications as apps
import synthetic_bench as bench

print('Build:', (root / '.abs-build-manifest.json').read_text())
rng = np.random.default_rng(20260909)
rng.standard_normal((512, 32))
rng.standard_normal(32)
spec = bench.build_cases(rng, 1.0, True)[0]
a, b, _ = spec['gen'](rng)
assert spec['case_id'] == 'tall.8000x32'
output = np.zeros(11)
lib = bench.load_router(root / 'libaffine_bundle_solver.so')
lib.bsolve_router_meta_api(bench.ptr(a), bench.ptr(b), None, *a.shape,
                          1, 2, 2, 20260909, 0, bench.ptr(output))
print('tall.8000x32 output', output.tolist())
assert list(output[[0, 2, 3, 4]]) == [1, 32, 32, 32] and output[10] <= 1e-14
lib = apps.load()
for case, a, b, x, seed in [
    ('N64_gauge', *apps.radio_complete(64, seed=1001), 93000),
    ('L7_equator', *apps.make_harmonic(7, 4096, 'equator', 2107), 94008),
]:
    out = apps.router(lib, a, b, x, seed, 4)
    print('application', case, 'status/rank/lo/hi', out[[0,2,3,4]].tolist())
apps.omp_threads(1)
runpy.run_path(str(root / 'tests/test_status_profile_semantics.py'), run_name='__main__')
orbits = orbit.run('full').compact()
print('full-scope orbit results', orbits['checks'], orbits['failure_counts_by_severity'],
      orbits['failure_counts_by_property'])
assert orbits['checks'] == 8335 and set(orbits['failure_counts_by_severity']) <= {'known-representation'}
old_check = cert.Report.check
samples = defaultdict(list)


def observe(self, prop, ok, **ctx):
    if prop == 'high_precision_outward_radius':
        samples[ctx['type']].append((ctx['e'], ctx['shadow']))
    return old_check(self, prop, ok, **ctx)


cert.Report.check = observe
focused = cert.run('full').out()
print('certificate battery', json.dumps(focused, indent=2))
assert focused['checks'] == 2271 and not focused['failures']
for typ, values in samples.items():
    print('type, count, distinct scale exponents, distinct shadow values', typ,
          len(values), sorted({e for e, q in values}), sorted({q for e, q in values}))
