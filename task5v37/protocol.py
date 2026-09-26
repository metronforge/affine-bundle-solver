"""Immutable v3.7 schedule and crash-preserving worker execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from task5v31.campaign import atomic_write, canonical_json
from task5v36.protocol import _arm, build_schedule
from task5v36.runtime import CONFIGURATIONS
from task5v37 import CAMPAIGN_ID
from task5v37.runtime import bootstrap_environment


def _protocol_digest(protocol):
    return hashlib.sha256(canonical_json(protocol)).hexdigest()


def run_dataset(schedule, *, runner, checkpoint, protocol):
    checkpoint = Path(checkpoint)
    digest = _protocol_digest(protocol)
    if checkpoint.exists():
        report = json.loads(checkpoint.read_text())
        if report.get("protocol_sha256") != digest:
            raise ValueError("checkpoint protocol mismatch")
    else:
        report = {"campaign_id": CAMPAIGN_ID, "protocol": protocol,
                  "protocol_sha256": digest, "records": [], "complete": False}
    completed = {row["observation_id"] for row in report["records"]}
    expected = {row["observation_id"] for row in schedule}
    if not completed <= expected:
        raise ValueError("checkpoint contains observation outside schedule")
    for item in schedule:
        if item["observation_id"] in completed:
            continue
        row = dict(item)
        try:
            row["record"] = runner(item)
        except subprocess.CalledProcessError as exc:
            row["execution_failure"] = {
                "type": type(exc).__name__, "message": str(exc),
                "returncode": exc.returncode, "stdout": exc.stdout or "",
                "stderr": exc.stderr or "", "command": exc.cmd,
            }
        except (subprocess.SubprocessError, OSError, ValueError, RuntimeError) as exc:
            row["execution_failure"] = {"type": type(exc).__name__,
                                        "message": str(exc)}
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
        policy = config.roles["legacy" if role in ("legacy", "mixed") else "solver"]
        environment = os.environ.copy()
        environment.update(bootstrap_environment(policy))
        environment["PYTHONHASHSEED"] = "0"
        command = ["taskset", "-c", config.cpu_set, sys.executable, "-m",
                   "task5v36.worker", "--role", role, "--configuration",
                   configuration, "--bundle", str(Path(bundles[item["slot_id"]]).resolve()),
                   "--library", str(Path(spec["library"]).resolve())]
        started = time.perf_counter_ns()
        completed = subprocess.run(command, check=False, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=environment, timeout=timeout_seconds)
        elapsed = time.perf_counter_ns() - started
        if completed.returncode:
            raise subprocess.CalledProcessError(
                completed.returncode, command, completed.stdout, completed.stderr)
        record = json.loads(completed.stdout)
        record.update({"command": command, "stderr": completed.stderr,
                       "worker_process_wall_ns": elapsed,
                       "process_returncode": completed.returncode,
                       "bootstrap_openblas_threads": environment["OPENBLAS_NUM_THREADS"]})
        return record
    return run


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
        "campaign_id": CAMPAIGN_ID, "protocol_revision": "v3.7-bootstrap-safe-openblas",
        "dataset": args.dataset, "configuration": args.configuration,
        "configuration_policy": repr(CONFIGURATIONS[args.configuration]),
        "arms": arms, "bundles": {key: str(value.resolve()) for key, value in bundles.items()},
        "slots": args.slots, "repetitions": args.repetitions,
        "warmups": args.warmups, "seed": args.seed,
        "timeout_seconds": args.timeout_seconds,
        "bootstrap_policy": "max(system_openblas_threads,scipy_blas_threads)",
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
