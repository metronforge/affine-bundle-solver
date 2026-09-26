"""Deterministic schedules and atomic no-rerun execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

from task5v31.campaign import atomic_write, canonical_json
from task5v36.campaign import CAMPAIGN_ID
from task5v36.runtime import CONFIGURATIONS, environment_for


def balanced_orders(arms, *, repetitions, seed, slot_index):
    arms = tuple(arms)
    if not arms or repetitions < 1:
        raise ValueError("arms and repetitions must be non-empty")
    rng = random.Random(seed + slot_index)
    if len(arms) == 2:
        # Preserve the already-sealed C1/C2 calibration schedule byte-for-byte.
        block_count = (repetitions + 1) // 2
        orders = []
        for _ in range(block_count):
            base = list(arms)
            rng.shuffle(base)
            rows = [tuple(base[offset:] + base[:offset]) for offset in range(2)]
            rng.shuffle(rows)
            orders.extend(rows)
        while len(orders) > repetitions:
            del orders[rng.randrange(len(orders))]
        return orders
    orders = []
    for _ in range(repetitions // len(arms)):
        base = list(arms)
        rng.shuffle(base)
        rows = [tuple(base[offset:] + base[:offset]) for offset in range(len(base))]
        rng.shuffle(rows)
        orders.extend(rows)
    remainder = repetitions % len(arms)
    if remainder:
        base = list(arms)
        rng.shuffle(base)
        rows = [tuple(base[offset:] + base[:offset]) for offset in range(len(base))]
        rng.shuffle(rows)
        orders.extend(rows[:remainder])
    return orders


def build_schedule(dataset, arms, slots, *, repetitions, warmups, seed):
    arms, slots = tuple(arms), tuple(slots)
    result = []
    for slot_index, slot in enumerate(slots):
        for warmup in range(warmups):
            order = arms if (slot_index + warmup) % 2 == 0 else tuple(reversed(arms))
            for position, arm in enumerate(order):
                result.append({"dataset": dataset, "slot_id": slot, "phase": "warmup",
                               "warmup": warmup, "arm": arm, "order": list(order),
                               "position": position,
                               "observation_id": f"{dataset}:{slot}:warmup:{warmup}:{arm}"})
        for trial, order in enumerate(balanced_orders(
                arms, repetitions=repetitions, seed=seed, slot_index=slot_index)):
            for position, arm in enumerate(order):
                result.append({"dataset": dataset, "slot_id": slot, "phase": "eligible",
                               "trial": trial, "arm": arm, "order": list(order),
                               "position": position,
                               "observation_id": f"{dataset}:{slot}:eligible:{trial}:{arm}"})
    return result


def _protocol_digest(protocol):
    return hashlib.sha256(canonical_json(protocol)).hexdigest()


def run_dataset(schedule, *, runner, checkpoint, protocol):
    checkpoint = Path(checkpoint)
    digest = _protocol_digest(protocol)
    if checkpoint.is_file():
        report = json.loads(checkpoint.read_text())
        if report.get("protocol_sha256") != digest:
            raise ValueError("checkpoint protocol mismatch")
    else:
        report = {"campaign_id": CAMPAIGN_ID, "protocol": protocol,
                  "protocol_sha256": digest, "records": [], "complete": False}
    by_id = {row["observation_id"]: row for row in report["records"]}
    schedule_ids = {item["observation_id"] for item in schedule}
    if not set(by_id) <= schedule_ids:
        raise ValueError("checkpoint contains observation outside schedule")
    for item in schedule:
        if item["observation_id"] in by_id:
            continue
        row = dict(item)
        try:
            row["record"] = runner(item)
        except (subprocess.SubprocessError, OSError, ValueError, RuntimeError) as exc:
            row["execution_failure"] = {"type": type(exc).__name__, "message": str(exc)}
        report["records"].append(row)
        atomic_write(checkpoint, canonical_json(report))
    report["complete"] = len(report["records"]) == len(schedule)
    atomic_write(checkpoint, canonical_json(report))
    return report


def worker_runner(*, arms, bundles, configuration, timeout_seconds=30):
    config = CONFIGURATIONS[configuration]

    def run(item):
        spec = arms[item["arm"]]
        role = spec.get("role", "solver")
        policy_name = "legacy" if role in ("legacy", "mixed") else "solver"
        policy = config.roles[policy_name]
        environment = os.environ.copy()
        environment.update(environment_for(policy))
        environment["PYTHONHASHSEED"] = "0"
        command = ["taskset", "-c", config.cpu_set, sys.executable, "-m",
                   "task5v36.worker", "--role", role, "--configuration",
                   configuration, "--bundle", str(Path(bundles[item["slot_id"]]).resolve()),
                   "--library", str(Path(spec["library"]).resolve())]
        worker_started = time.perf_counter_ns()
        completed = subprocess.run(command, check=True, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=environment, timeout=timeout_seconds)
        worker_wall_ns = time.perf_counter_ns() - worker_started
        record = json.loads(completed.stdout)
        record["command"] = command
        record["stderr"] = completed.stderr
        record["worker_process_wall_ns"] = worker_wall_ns
        return record
    return run


def _arm(value):
    try:
        name, role, library = value.split("=", 2)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("arm must be NAME=ROLE=LIBRARY") from exc
    if role not in ("solver", "legacy", "mixed"):
        raise argparse.ArgumentTypeError(f"unsupported role: {role}")
    return name, {"role": role, "library": library}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--configuration", choices=tuple(CONFIGURATIONS), required=True)
    parser.add_argument("--arm", action="append", type=_arm, required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--slots", nargs="+", required=True)
    parser.add_argument("--repetitions", type=int, required=True)
    parser.add_argument("--warmups", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    args = parser.parse_args()
    arms = dict(args.arm)
    bundles = {slot: args.bundle_root / slot for slot in args.slots}
    schedule = build_schedule(args.dataset, tuple(arms), tuple(args.slots),
                              repetitions=args.repetitions,
                              warmups=args.warmups, seed=args.seed)
    protocol = {
        "campaign_id": CAMPAIGN_ID, "dataset": args.dataset,
        "configuration": args.configuration,
        "configuration_policy": repr(CONFIGURATIONS[args.configuration]),
        "arms": arms, "bundles": {key: str(value.resolve())
                                    for key, value in bundles.items()},
        "slots": args.slots, "repetitions": args.repetitions,
        "warmups": args.warmups, "seed": args.seed,
        "timeout_seconds": args.timeout_seconds,
        "selective_exclusions": False, "selective_reruns": False,
    }
    report = run_dataset(
        schedule,
        runner=worker_runner(arms=arms, bundles=bundles,
                             configuration=args.configuration,
                             timeout_seconds=args.timeout_seconds),
        checkpoint=args.checkpoint, protocol=protocol)
    failures = sum("execution_failure" in row for row in report["records"])
    print(json.dumps({"checkpoint": str(args.checkpoint),
                      "records": len(report["records"]),
                      "complete": report["complete"],
                      "execution_failures": failures}, sort_keys=True))


if __name__ == "__main__":
    main()
