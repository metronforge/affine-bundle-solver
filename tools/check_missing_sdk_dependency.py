"""Non-destructive missing-dependency negative controls on disposable DSO copies."""
import ctypes
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    prefix, audit_path, output = map(Path, sys.argv[1:])
    audit = json.loads(audit_path.read_text())
    router = next(x for x in audit['libraries'] if 'libaffine_bundle_solver' in x['path'])
    original = prefix / router['path']
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    evidence = []
    for category, needle in [('blas', 'blas'), ('openmp', 'omp')]:
        dependency = next(x for x in router['needed'] if needle in x)
        with tempfile.TemporaryDirectory(prefix='abs-missing-dependency-') as tmp:
            copy = Path(tmp) / original.name
            shutil.copy2(original, copy)
            absent = str(Path(tmp) / ('abs-intentionally-missing-' + category + original.suffix))
            if sys.platform == 'darwin':
                subprocess.run(['install_name_tool', '-change', dependency, absent, str(copy)], check=True)
                subprocess.run(['codesign', '--force', '--sign', '-', str(copy)], check=True)
            else:
                subprocess.run(['patchelf', '--replace-needed', dependency, absent, str(copy)], check=True)
            result = subprocess.run([sys.executable, '-c',
                                     'import ctypes,sys; ctypes.CDLL(sys.argv[1])', str(copy)],
                                    text=True, capture_output=True)
            if result.returncode == 0 or absent not in result.stderr:
                raise RuntimeError(f'{category}: missing dependency did not produce expected loader failure: {result}')
            evidence.append(dict(category=category, dependency=dependency,
                                 returncode=result.returncode, error=result.stderr,
                                 method='disposable DSO required-name substitution; system unchanged'))
    assert hashlib.sha256(original.read_bytes()).hexdigest() == digest
    output.write_text(json.dumps(evidence, indent=2) + '\n')
    print('Missing BLAS/OpenMP negative controls: PASS; original SDK unchanged')


if __name__ == '__main__':
    main()
