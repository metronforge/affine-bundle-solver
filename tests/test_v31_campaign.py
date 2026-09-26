import hashlib

from task5v31.campaign import (
    CAMPAIGN_ID,
    canonical_json,
    canonical_jsonl,
    generate_ledger,
    generate_manifest,
    validate_ledger,
    validate_manifest,
)


def test_v31_manifest_and_ledger_are_new_identity_and_byte_stable():
    first = canonical_json(generate_manifest())
    second = canonical_json(generate_manifest())
    assert first == second
    manifest = generate_manifest()
    assert manifest["campaign_id"] == "task5-v3.1-performance-20260926"
    assert len(manifest["slots"]) == 27
    assert [slot["slot_id"] for slot in manifest["slots"]] == [f"V31-{i:03d}" for i in range(1, 28)]
    assert sum(slot["eligibility"]["small"] for slot in manifest["slots"]) == 24
    assert sum(slot["eligibility"]["bounded_large"] for slot in manifest["slots"]) == 3
    validate_manifest(manifest)
    digest = hashlib.sha256(first).hexdigest()
    ledger = generate_ledger(manifest, digest)
    validate_ledger(manifest, ledger, digest)
    assert canonical_jsonl(ledger) == canonical_jsonl(generate_ledger(generate_manifest(), digest))
    assert {row["initial_state"] for row in ledger} == {"READY_SMALL", "DEFERRED_BOUNDED_LARGE"}
    assert CAMPAIGN_ID == manifest["campaign_id"]
