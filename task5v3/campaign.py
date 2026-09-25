"""Generate a new deterministic Task-5 v3 manifest and initial ledger."""

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

CAMPAIGN_ID = "task5-v3-canonical-20260925"
SCHEMA_VERSION = 3
PROFILES = {"full", "exact_deficient", "near_low", "near_high", "zero", "scaled_pair"}


def canonical_json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def canonical_jsonl(rows):
    return b"".join(canonical_json(row) for row in rows)


def _slot(index, shape, m, n, profile, rhs, scale=1.0, resource="UNIT", mode="FULL"):
    rank = 0 if profile == "zero" else min(m, n) - 1 if profile == "exact_deficient" else min(m, n)
    small = resource == "UNIT"
    near = {"near_low": 5e-12, "near_high": 5e-10, "scaled_pair": 1e-10}.get(profile)
    return {
        "slot_id": f"V3-{index + 1:03d}", "deterministic_order_index": index,
        "case_family": "diagonal_profile", "shape_class": shape,
        "m": m, "n": n, "seed": 2026092500 + index,
        "generator_parameters": {"profile": profile, "scale": scale, "near_singular": near},
        "structural_rank_profile": {"algebraic_rank": rank, "profile": profile},
        "rhs_policy": rhs, "standard_oracle_mode": mode,
        "expected_resource_class": resource, "max_dimension": max(m, n),
        "eligibility": {"small": small, "bounded_large": not small},
        "router_strategy_intent": "ambiguous_rank" if profile.startswith("near_") else
                                  "rank_zero" if profile == "zero" else
                                  "rank_deficient" if profile == "exact_deficient" else
                                  "clear_full_rank",
    }


def generate_manifest():
    slots = []

    def add(shape, m, n, profile, rhs="compatible", scale=1.0, resource="UNIT", mode="FULL"):
        slots.append(_slot(len(slots), shape, m, n, profile, rhs, scale, resource, mode))

    for shape, m, n in (("wide", 3, 5), ("square", 4, 4), ("tall", 5, 3)):
        add(shape, m, n, "full")
        add(shape, m, n, "exact_deficient", mode="QR")
        add(shape, m, n, "exact_deficient", "incompatible", mode="QR")
        add(shape, m, n, "near_low")
        add(shape, m, n, "near_high", mode="QR")
        add(shape, m, n, "zero", mode="QR")
        add(shape, m, n, "zero", "incompatible", mode="QR")
    add("square", 2, 2, "scaled_pair", scale=1.0)
    add("square", 2, 2, "scaled_pair", scale=1e8)
    add("tall", 5, 3, "full", "incompatible")
    for shape, m, n in (("wide", 128, 256), ("square", 192, 192), ("tall", 256, 128)):
        add(shape, m, n, "full", resource="BOUNDED_LARGE", mode="QR")
    result = {"campaign_id": CAMPAIGN_ID, "schema_version": SCHEMA_VERSION,
              "coverage_model": "v3-diagonal-profile-analytic-rhs", "slots": slots}
    validate_manifest(result)
    return result


def validate_manifest(value):
    if value.get("campaign_id") != CAMPAIGN_ID or value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("wrong campaign identity")
    slots = value.get("slots")
    if not isinstance(slots, list) or not slots:
        raise ValueError("empty slot list")
    ids, orders = set(), set()
    for slot in slots:
        sid, order = slot["slot_id"], slot["deterministic_order_index"]
        if sid in ids:
            raise ValueError("duplicate slot ID")
        if order in orders:
            raise ValueError("duplicate order index")
        ids.add(sid)
        orders.add(order)
        m, n = slot["m"], slot["n"]
        if type(m) is not int or type(n) is not int or m <= 0 or n <= 0:
            raise ValueError("invalid dimensions")
        if slot["max_dimension"] != max(m, n):
            raise ValueError("wrong maximum dimension")
        if slot["shape_class"] != ("wide" if m < n else "tall" if m > n else "square"):
            raise ValueError("wrong shape class")
        params = slot["generator_parameters"]
        profile, scale = params["profile"], params["scale"]
        if profile not in PROFILES or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
            raise ValueError("invalid generator parameters")
        rank = 0 if profile == "zero" else min(m, n) - 1 if profile == "exact_deficient" else min(m, n)
        if slot["structural_rank_profile"]["algebraic_rank"] != rank:
            raise ValueError("wrong algebraic rank profile")
        if slot["rhs_policy"] not in ("compatible", "incompatible"):
            raise ValueError("invalid RHS policy")
        if slot["rhs_policy"] == "incompatible" and m <= rank:
            raise ValueError("incompatible RHS impossible for full-row-rank input")
        if slot["standard_oracle_mode"] not in ("FULL", "QR"):
            raise ValueError("invalid standard oracle mode")
        eligible = slot["eligibility"]
        if eligible["small"] == eligible["bounded_large"] or eligible["small"] != (slot["expected_resource_class"] == "UNIT"):
            raise ValueError("resource class/eligibility mismatch")
    if orders != set(range(len(slots))) or [s["deterministic_order_index"] for s in slots] != list(range(len(slots))):
        raise ValueError("noncontiguous deterministic order")


def generate_ledger(manifest, digest):
    validate_manifest(manifest)
    rows = []
    for slot in manifest["slots"]:
        small = slot["eligibility"]["small"]
        rows.append({"campaign_id": CAMPAIGN_ID, "manifest_sha256": digest,
                     "slot_id": slot["slot_id"], "deterministic_order_index": slot["deterministic_order_index"],
                     "initial_state": "READY_SMALL" if small else "DEFERRED_BOUNDED_LARGE",
                     "eligibility_reason": "unit-scale validation" if small else "future bounded-large validation only",
                     "creation_provenance": "task5v3.campaign.generate_ledger from canonical manifest"})
    validate_ledger(manifest, rows, digest)
    return rows


def validate_ledger(manifest, rows, digest):
    validate_manifest(manifest)
    if len(rows) != len(manifest["slots"]):
        raise ValueError("ledger length or duplicate mismatch")
    seen = set()
    for slot, row in zip(manifest["slots"], rows):
        sid = row["slot_id"]
        if sid in seen:
            raise ValueError("duplicate ledger slot")
        seen.add(sid)
        if row["manifest_sha256"] != digest:
            raise ValueError("manifest hash mismatch")
        if row["campaign_id"] != CAMPAIGN_ID or sid != slot["slot_id"] or row["deterministic_order_index"] != slot["deterministic_order_index"]:
            raise ValueError("ledger slot/order mismatch")
        small = slot["eligibility"]["small"]
        if row["initial_state"] != ("READY_SMALL" if small else "DEFERRED_BOUNDED_LARGE"):
            raise ValueError("ledger eligibility mismatch")


def atomic_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = generate_manifest()
    manifest_bytes = canonical_json(manifest)
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    atomic_write(args.out / "manifest.json", manifest_bytes)
    atomic_write(args.out / "execution-ledger.jsonl", canonical_jsonl(generate_ledger(manifest, digest)))
    print(f"manifest_sha256={digest} slots={len(manifest['slots'])}")


if __name__ == "__main__":
    main()
