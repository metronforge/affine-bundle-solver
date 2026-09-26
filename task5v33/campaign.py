"""Immutable identity and frozen slot manifest for Task-5 v3.3."""

import argparse
import copy
import hashlib
from pathlib import Path

from task5v31.campaign import atomic_write, canonical_json, generate_manifest

CAMPAIGN_ID = "task5-v3.3-reusable-qrcp-20260926"
CONTROL_SOLVER = "f66cd87a7b198497cc53d63b2bb04b85c3e64f53"
CANDIDATE_SOLVER = "1621d104a27eef3b12ec291384cac5f517da79f4"
REVIEWED_SOLVER = "87b239745f38514286a7a9d29f11b1a59f5b8245"
SOLVER_TREE = "86dd1f677664160e40de72c0121e72fa5e54a83b"
HARNESS_CAMPAIGN_BASELINE = "4e2a6a0183dac1201e99ca083e6a67c45716c4c2"
HARNESS_DESIGN_BASELINE = "1827f2d458bcf55b0ade81a1174d1fa2ceb9d9ad"


def generate_v33_manifest():
    manifest = copy.deepcopy(generate_manifest())
    manifest["campaign_id"] = CAMPAIGN_ID
    manifest["schema_version"] = 33
    manifest["purpose"] = "reusable QRCP implementation validation"
    manifest["canonical_campaign_gate"] = "run only if frozen three-slot geometric-mean speedup is at least 1.5x"
    manifest["frozen_baselines"] = {
        "solver_control_commit": CONTROL_SOLVER,
        "solver_candidate_commit": CANDIDATE_SOLVER,
        "solver_reviewed_head": REVIEWED_SOLVER,
        "solver_candidate_tree": SOLVER_TREE,
        "harness_campaign_baseline": HARNESS_CAMPAIGN_BASELINE,
        "harness_design_baseline": HARNESS_DESIGN_BASELINE,
        "thread_count": 4,
    }
    return manifest


def manifest_bytes():
    return canonical_json(generate_v33_manifest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    payload = manifest_bytes()
    atomic_write(args.out, payload)
    print(f"manifest_sha256={hashlib.sha256(payload).hexdigest()} slots=27")


if __name__ == "__main__":
    main()
