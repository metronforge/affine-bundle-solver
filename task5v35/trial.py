"""One process-isolated Task-5 v3.5 trial with loaded-library evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from task5v31.campaign import generate_manifest
from task5v31.runner import json_safe, run_case


def loaded_numeric_libraries():
    names = set()
    for line in Path("/proc/self/maps").read_text().splitlines():
        path = line.split()[-1] if "/" in line else ""
        lower = path.lower()
        if any(token in lower for token in ("blas", "lapack", "mkl", "gomp", "iomp")):
            names.add(path)
    return sorted(names)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", required=True)
    parser.add_argument("--legacy-preliminary-xt", action="store_true")
    args = parser.parse_args()
    slot = next(item for item in generate_manifest()["slots"]
                if item["slot_id"] == args.slot)
    row = run_case(slot, legacy_preliminary_xt=args.legacy_preliminary_xt)
    row["process_affinity"] = sorted(os.sched_getaffinity(0))
    row["loaded_numeric_libraries"] = loaded_numeric_libraries()
    print(json.dumps(json_safe(row), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

