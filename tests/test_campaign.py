import hashlib
import json

import pytest

from task5v3.campaign import (
    CAMPAIGN_ID,
    canonical_json,
    canonical_jsonl,
    generate_ledger,
    generate_manifest,
    validate_ledger,
    validate_manifest,
)


def test_new_manifest_covers_declared_matrix_without_historical_ids():
    manifest = generate_manifest()
    validate_manifest(manifest)
    slots = manifest["slots"]
    assert len(slots) == 27
    assert [s["slot_id"] for s in slots] == [f"V3-{i:03d}" for i in range(1, 28)]
    assert [s["deterministic_order_index"] for s in slots] == list(range(27))
    assert {s["case_family"] for s in slots} == {"diagonal_profile"}
    assert {s["shape_class"] for s in slots} == {"wide", "square", "tall"}
    assert {s["generator_parameters"]["profile"] for s in slots} == {
        "full", "exact_deficient", "near_low", "near_high", "zero", "scaled_pair"
    }
    assert {s["rhs_policy"] for s in slots} == {"compatible", "incompatible"}
    assert sum(s["eligibility"]["small"] for s in slots) == 24
    assert sum(s["eligibility"]["bounded_large"] for s in slots) == 3
    assert max(s["max_dimension"] for s in slots if s["eligibility"]["small"]) <= 5
    assert manifest["campaign_id"] == CAMPAIGN_ID


def test_manifest_generation_is_byte_identical_and_rejects_duplicates():
    a = canonical_json(generate_manifest())
    b = canonical_json(generate_manifest())
    assert a == b and a.endswith(b"\n")
    manifest = json.loads(a)
    manifest["slots"][1]["slot_id"] = manifest["slots"][0]["slot_id"]
    with pytest.raises(ValueError, match="duplicate slot ID"):
        validate_manifest(manifest)
    manifest = json.loads(a)
    manifest["slots"][1]["deterministic_order_index"] = 0
    with pytest.raises(ValueError, match="duplicate order index"):
        validate_manifest(manifest)


def test_ledger_is_manifest_bound_bijective_and_ordered():
    manifest = generate_manifest()
    digest = hashlib.sha256(canonical_json(manifest)).hexdigest()
    rows = generate_ledger(manifest, digest)
    validate_ledger(manifest, rows, digest)
    assert len(rows) == len(manifest["slots"])
    assert canonical_jsonl(rows) == canonical_jsonl(generate_ledger(generate_manifest(), digest))
    assert {row["initial_state"] for row in rows} == {"READY_SMALL", "DEFERRED_BOUNDED_LARGE"}
    bad = rows + [rows[0]]
    with pytest.raises(ValueError, match="duplicate"):
        validate_ledger(manifest, bad, digest)
    bad = [dict(row) for row in rows]
    bad[0]["manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="manifest hash"):
        validate_ledger(manifest, bad, digest)
