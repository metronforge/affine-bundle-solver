"""Frozen ordering and execution helpers for Task-5 v3.5."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
from pathlib import Path

from task5v31.campaign import atomic_write, canonical_json
from task5v31.runner import json_safe


ARMS = ("L", "M", "F", "A")
SLOTS = ("V31-025", "V31-026", "V31-027")
THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                    "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def balanced_orders(arms, *, repetitions, seed, slot_index):
    arms = tuple(arms)
    if not arms or repetitions < 1:
        raise ValueError("arms and repetitions must be non-empty")
    rng = random.Random(seed + slot_index)
    block_count = (repetitions + len(arms) - 1) // len(arms)
    orders = []
    for _ in range(block_count):
        base = list(arms)
        rng.shuffle(base)
        rows = [tuple(base[offset:] + base[:offset]) for offset in range(len(base))]
        rng.shuffle(rows)
        orders.extend(rows)
    if len(orders) > repetitions:
        del orders[rng.randrange(len(orders))]
    return orders


def trial_command(slot_id, arm, libraries, *, cpu_set):
    command = ["taskset", "-c", cpu_set, sys.executable, "-m", "task5v35.trial",
               "--slot", slot_id]
    if arm == "L":
        command.append("--legacy-preliminary-xt")
    return command


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def execute_trial(slot_id, arm, libraries, *, cpu_set, thread_values):
    library = Path(libraries[arm]).resolve()
    environment = os.environ.copy()
    environment.update(thread_values)
    environment["TASK5_SOLVER_LIB"] = str(library)
    environment["LD_LIBRARY_PATH"] = str(library.parent)
    command = trial_command(slot_id, arm, libraries, cpu_set=cpu_set)
    completed = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=environment)
    record = json.loads(completed.stdout)
    record["arm"] = arm
    record["library"] = {"path": str(library), "sha256": _sha256(library)}
    return record


def execute_dense_trial(slot_id, arm, libraries, *, cpu_set, thread_values):
    library = Path(libraries[arm]).resolve()
    environment = os.environ.copy()
    environment.update(thread_values)
    environment["TASK5_SOLVER_LIB"] = str(library)
    environment["LD_LIBRARY_PATH"] = str(library.parent)
    command = ["taskset", "-c", cpu_set, sys.executable, "-m", "task5v35.dense",
               "--slot", slot_id]
    completed = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=environment)
    record = json.loads(completed.stdout)
    record["arm"] = arm
    record["library"] = {"path": str(library), "sha256": _sha256(library)}
    return record


def run_dataset(libraries, *, repetitions, warmups, seed, cpu_set,
                arms=ARMS, slots=SLOTS, checkpoint=None, thread_values=None):
    arms = tuple(arms)
    slots = tuple(slots)
    threads = ({name: "4" for name in THREAD_VARIABLES}
               if thread_values is None else dict(thread_values))
    report = {
        "campaign_id": "task5-v3.5-row-axpy-qualification-20260926",
        "protocol": {"arms": list(arms), "slots": list(slots),
                     "warmups_per_arm_slot": warmups,
                     "eligible_trials_per_arm_slot": repetitions,
                     "seed": seed, "cpu_set": cpu_set,
                     "thread_environment": threads,
                     "selective_reruns": False},
        "records": [],
    }

    def append(item):
        report["records"].append(item)
        if checkpoint is not None:
            atomic_write(checkpoint, canonical_json(json_safe(report)))

    for slot_index, slot_id in enumerate(slots):
        for warmup in range(warmups):
            for arm in arms:
                append({"slot_id": slot_id, "phase": "warmup", "warmup": warmup,
                        "arm": arm, "order": list(arms),
                        "record": execute_trial(slot_id, arm, libraries,
                                                cpu_set=cpu_set,
                                                thread_values=threads)})
        orders = balanced_orders(arms, repetitions=repetitions, seed=seed,
                                 slot_index=slot_index)
        for trial, order in enumerate(orders):
            for arm in order:
                append({"slot_id": slot_id, "phase": "eligible", "trial": trial,
                        "arm": arm, "order": list(order),
                        "record": execute_trial(slot_id, arm, libraries,
                                                cpu_set=cpu_set,
                                                thread_values=threads)})
    return report


def run_dense_dataset(libraries, *, seed, cpu_set, checkpoint=None):
    arms = ("M", "A")
    threads = {name: "4" for name in THREAD_VARIABLES}
    report = {"campaign_id": "task5-v3.5-row-axpy-dense-secondary-20260926",
              "protocol": {"arms": list(arms), "slots": list(SLOTS),
                           "warmups_per_arm_slot": 1,
                           "eligible_trials_per_arm_slot": 11,
                           "seed": seed, "cpu_set": cpu_set,
                           "thread_environment": threads,
                           "selective_reruns": False, "gating": False},
              "records": []}

    def append(item):
        report["records"].append(item)
        if checkpoint is not None:
            atomic_write(checkpoint, canonical_json(json_safe(report)))

    for slot_index, slot_id in enumerate(SLOTS):
        for arm in arms:
            append({"slot_id": slot_id, "phase": "warmup", "warmup": 0,
                    "arm": arm, "order": list(arms),
                    "record": execute_dense_trial(slot_id, arm, libraries,
                                                  cpu_set=cpu_set,
                                                  thread_values=threads)})
        for trial, order in enumerate(balanced_orders(
                arms, repetitions=11, seed=seed, slot_index=slot_index)):
            for arm in order:
                append({"slot_id": slot_id, "phase": "eligible", "trial": trial,
                        "arm": arm, "order": list(order),
                        "record": execute_dense_trial(slot_id, arm, libraries,
                                                      cpu_set=cpu_set,
                                                      thread_values=threads)})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm-library", action="append", required=True,
                        help="ARM=/absolute/path/libcertified_solver.so")
    parser.add_argument("--arms", nargs="+", required=True)
    parser.add_argument("--slots", nargs="+", default=list(SLOTS))
    parser.add_argument("--repetitions", type=int, required=True)
    parser.add_argument("--warmups", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--cpu-set", required=True)
    parser.add_argument("--thread-value", action="append", default=[],
                        help="NAME=VALUE override; omitted variables default to four")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    libraries = dict(item.split("=", 1) for item in args.arm_library)
    threads = {name: "4" for name in THREAD_VARIABLES}
    threads.update(dict(item.split("=", 1) for item in args.thread_value))
    report = run_dataset(libraries, repetitions=args.repetitions,
                         warmups=args.warmups, seed=args.seed,
                         cpu_set=args.cpu_set, arms=args.arms, slots=args.slots,
                         checkpoint=args.out, thread_values=threads)
    print(json.dumps({"records": len(report["records"]), "out": str(args.out)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
