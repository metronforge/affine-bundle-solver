import hashlib


def test_v33_manifest_is_deterministic_and_preserves_frozen_27_slot_design():
    from task5v33.campaign import CAMPAIGN_ID, manifest_bytes

    first = manifest_bytes()
    second = manifest_bytes()
    assert first == second
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()

    import json
    manifest = json.loads(first)
    assert manifest["campaign_id"] == CAMPAIGN_ID
    assert len(manifest["slots"]) == 27
    assert [slot["slot_id"] for slot in manifest["slots"][-3:]] == ["V31-025", "V31-026", "V31-027"]
    assert all(slot["eligibility"]["bounded_large"] for slot in manifest["slots"][-3:])
    assert manifest["frozen_baselines"]["solver_control_commit"].startswith("f66cd87")
    assert manifest["frozen_baselines"]["solver_candidate_commit"].startswith("1621d104")
