"""Untimed deterministic input/oracle bundles for isolated workers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from task5v31.campaign import atomic_write, canonical_json, generate_manifest
from task5v31.materialize import materialize
from task5v31.oracles import contract_oracle, standard_oracle
from task5v31.runner import json_safe


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def write_bundle(slot, path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    a, b, matrix = materialize(slot)
    standard, _ = standard_oracle(a, b, slot)
    contract, _ = contract_oracle(a, b)
    a_bytes, b_bytes = a.tobytes(order="C"), b.tobytes(order="C")
    atomic_write(path / "a.f64le", a_bytes)
    atomic_write(path / "b.f64le", b_bytes)
    metadata = {
        "slot": slot, "matrix": matrix, "dtype": "float64-le-c-order",
        "matrix_sha256": _digest(a_bytes), "rhs_sha256": _digest(b_bytes),
        "standard_oracle": standard, "contract_oracle": contract,
    }
    atomic_write(path / "metadata.json", canonical_json(json_safe(metadata)))
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--slots", nargs="*")
    args = parser.parse_args()
    slots = generate_manifest()["slots"]
    if args.slots:
        wanted = set(args.slots)
        slots = [slot for slot in slots if slot["slot_id"] in wanted]
    result = {}
    for slot in slots:
        result[slot["slot_id"]] = write_bundle(slot, args.out / slot["slot_id"])
    print(json.dumps(json_safe(result), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

