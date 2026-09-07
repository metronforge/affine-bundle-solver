#!/usr/bin/env python3
import ctypes, importlib.util, json, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pbt', ROOT/'tests/pbt_equivalence_orbits.py')
pbt=importlib.util.module_from_spec(spec);spec.loader.exec_module(pbt)
pbt.FAST.bsolve_fg_counters_reset_api.argtypes=[]
pbt.FAST.bsolve_fg_counters_api.argtypes=[ctypes.POINTER(ctypes.c_ulonglong)]
pbt.FAST.bsolve_fg_counters_reset_api()
t0=time.perf_counter();R=pbt.run('full');elapsed=time.perf_counter()-t0
report=R.compact();out=(ctypes.c_ulonglong*3)();pbt.FAST.bsolve_fg_counters_api(out)
tele={'elapsed_s':elapsed,'checks':report['checks'],'failure_counts_by_severity':report['failure_counts_by_severity'],'formation_guard_checks':int(out[0]),'formation_escalations':int(out[1]),'source_qrcp_calls_total':int(out[2])}
(ROOT/'results/pbt_full_strict_guard.json').write_text(json.dumps(report,indent=2,allow_nan=True)+'\n')
(ROOT/'results/pbt_full_strict_guard_telemetry.json').write_text(json.dumps(tele,indent=2)+'\n')
print(json.dumps(tele,indent=2))
