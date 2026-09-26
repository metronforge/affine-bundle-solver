"""Bounded semantic validation with an explicitly propagated environment."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from task5v36.analysis import _meaningful_view


BASE_ENV = {
    "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1",
    "OMP_DYNAMIC": "FALSE", "MKL_DYNAMIC": "FALSE", "PYTHONHASHSEED": "0",
}


def run_worker(*, role, bundle, library, openblas_threads, timeout=30):
    environment = os.environ.copy()
    environment.update(BASE_ENV)
    environment["OPENBLAS_NUM_THREADS"] = str(openblas_threads)
    command = [
        "taskset", "-c", "1,3,6,8", sys.executable, "-m", "task5v36.worker",
        "--role", role, "--configuration", "C1", "--bundle",
        str(Path(bundle).resolve()), "--library", str(Path(library).resolve()),
    ]
    completed = subprocess.run(
        command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=environment, timeout=timeout,
    )
    if completed.returncode:
        return {
            "ok": False, "returncode": completed.returncode,
            "signal": -completed.returncode if completed.returncode < 0 else None,
            "stdout": completed.stdout, "stderr": completed.stderr,
            "command": command,
        }
    record = json.loads(completed.stdout)
    return {
        "ok": True, "returncode": 0, "command": command,
        "meaningful": _meaningful_view(record["combined"]), "record": record,
    }
