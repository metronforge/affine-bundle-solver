import subprocess

from task5v36.protocol import build_schedule


def test_v39_campaign_identity_and_focused_schedule():
    from task5v39 import CAMPAIGN_ID

    assert CAMPAIGN_ID == "task5-v3.9-corrected-verifier-20260926"
    schedule = build_schedule(
        "focused-v3.9", ("L", "M", "A"),
        ("V31-025", "V31-026", "V31-027"),
        repetitions=31, warmups=1, seed=2026093904,
    )
    assert len(schedule) == 288
    assert sum(row["phase"] == "eligible" for row in schedule) == 279
    assert len({row["observation_id"] for row in schedule}) == 288


def test_canonical_schedule_has_exact_frozen_accounting():
    slots = tuple(f"V31-{index:03d}" for index in range(1, 28))
    schedule = build_schedule(
        "canonical-v3.9", ("L", "M", "A"), slots,
        repetitions=5, warmups=1, seed=2026093606,
    )
    assert len(schedule) == 486
    assert sum(row["phase"] == "warmup" for row in schedule) == 81
    assert sum(row["phase"] == "eligible" for row in schedule) == 405
    assert len({row["observation_id"] for row in schedule}) == 486


def test_validation_passes_bootstrap_environment(monkeypatch, tmp_path):
    from task5v39.validation import run_worker

    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs["env"])
        return subprocess.CompletedProcess(command, 1, "", "intentional")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_worker(
        role="legacy", bundle=tmp_path, library=tmp_path / "lib.so",
        openblas_threads=4,
    )
    assert not result["ok"]
    assert captured["OPENBLAS_NUM_THREADS"] == "4"
    assert captured["OMP_NUM_THREADS"] == "1"
