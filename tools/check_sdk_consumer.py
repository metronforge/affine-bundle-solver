"""Run a consumer and prove every solver DSO loaded comes from this SDK."""
import os
from pathlib import Path
import re
import subprocess
import sys

prefix, executable = map(lambda x: Path(x).resolve(), sys.argv[1:])
env = dict(os.environ)
if sys.platform == 'darwin':
    env['DYLD_PRINT_LIBRARIES'] = '1'
    result = subprocess.run([str(executable)], env=env, text=True, capture_output=True, check=True)
    paths = re.findall(r'(/\S*lib(?:affine_bundle_solver|certified_solver|status_verifier)\.dylib)', result.stderr)
else:
    resolution = subprocess.check_output(['ldd', str(executable)], text=True)
    if 'not found' in resolution:
        raise RuntimeError(resolution)
    paths = re.findall(r'lib(?:affine_bundle_solver|certified_solver|status_verifier)\.so => (/\S+)', resolution)
    result = subprocess.run([str(executable)], text=True, capture_output=True, check=True)
if not paths or any(Path(p).resolve().parent != prefix / 'lib' for p in paths):
    raise RuntimeError(f'consumer did not resolve solver exclusively from extracted SDK: {paths}')
print('SDK resolution: ' + ', '.join(paths), file=sys.stderr)
print(result.stdout, end='')
