"""Immutable Task-5 v3.6 identity and 27-slot manifest."""

from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path

from task5v31.campaign import atomic_write, canonical_json, generate_manifest


CAMPAIGN_ID = "task5-v3.6-isolated-blas-20260926"
AUTHORIZED_MAIN = "bb6c30d03191a92695b16d21581bfea6dce9942e"
AUTHORIZED_MAIN_TREE = "e621eef836c2e6edd633c03d657cc582e0e04344"
CANDIDATE = "dd30ef900ff7f48d4fe97e79aae94b7e64c48741"
CANDIDATE_TREE = "a89ce2def1fc1b2ef4644cc4d17f13c533b099b7"
LEGACY_CONTROL = "f66cd87a7b198497cc53d63b2bb04b85c3e64f53"


def generate_v36_manifest():
    manifest = copy.deepcopy(generate_manifest())
    manifest.update({
        "campaign_id": CAMPAIGN_ID,
        "schema_version": 36,
        "purpose": "role-isolated BLAS qualification and complete Task-5 closure",
        "identities": {
            "accepted_main": AUTHORIZED_MAIN,
            "accepted_main_tree": AUTHORIZED_MAIN_TREE,
            "candidate": CANDIDATE,
            "candidate_tree": CANDIDATE_TREE,
            "legacy_control": LEGACY_CONTROL,
        },
        "protocol_revision": "v3.6-role-isolated-blas",
    })
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = canonical_json(generate_v36_manifest())
    atomic_write(args.out, raw)
    print(f"manifest_sha256={hashlib.sha256(raw).hexdigest()} slots=27")


if __name__ == "__main__":
    main()
