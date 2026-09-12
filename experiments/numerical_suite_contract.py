#!/usr/bin/env python3
"""Pure contract machinery for the main numerical-suite evidence package.

This module owns no numerical generators and makes no solver calls. Its public
functions are deliberately fixture-friendly so package, provenance, runtime,
and publication behavior can be tested without loading the solver library.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import statistics
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


RESULT_SCHEMA_VERSION = 2
METADATA_SCHEMA_VERSION = 2
PROTOCOL_ID = "affine-bundle-numerical-suite-v2"
RESULT_FILENAME = "numerical-suite-reference.json"
METADATA_FILENAME = "numerical-suite-reference.metadata.json"
CHECKSUM_FILENAME = "numerical-suite-reference.sha256"
BUILD_MANIFEST_NAME = ".abs-build-manifest.json"
ROUTER_BASENAME = "libaffine_bundle_solver.so"
DIGITS_DESIGN_SHA256 = \
    "e0fd0d6813a2c9672452920a25da74d0b2b8a2cef476cfad80ad4b4f52bb5355"

CANONICAL_SECTIONS = (
    ("standard", "standard"),
    ("rank", "rank_transition"),
    ("guard", "guard_timing"),
    ("scaling", "scaling"),
    ("structural", "structural"),
    ("lapack", "lapack_context"),
)


def _timing(operation: str, source: str, warmups: int,
            repetitions: int) -> dict[str, Any]:
    return {"operation": operation, "source": source,
            "warmups": warmups, "repetitions": repetitions}


def _case(case_id: str, section: str, generator: str, m: int, n: int,
          input_seeds: Sequence[int], *, expected_status: str,
          expected_rank: int, timings: Sequence[Mapping[str, Any]],
          routing_seeds: Sequence[int] = (),
          expected_rank_lo: int | None = None,
          expected_rank_hi: int | None = None) -> dict[str, Any]:
    lo = expected_rank if expected_rank_lo is None else expected_rank_lo
    hi = ((n if expected_status == "infinite" else expected_rank)
          if expected_rank_hi is None else expected_rank_hi)
    return {
        "case_id": case_id, "section": section, "generator": generator,
        "m": int(m), "n": int(n),
        "input_seeds": [int(seed) for seed in input_seeds],
        "routing_seeds": [int(seed) for seed in routing_seeds],
        "expected_status": expected_status, "expected_rank": expected_rank,
        "expected_rank_lo": lo, "expected_rank_hi": hi,
        "timings": [dict(item) for item in timings],
    }


def _build_cases() -> tuple[dict[str, Any], ...]:
    cases: list[dict[str, Any]] = []
    standard = (
        ("random64", "make_random", 32768, 64, 101, "unique", 64),
        ("grouped64", "make_grouped", 65536, 64, 102, "unique", 64),
        ("rankdef64", "make_random", 32768, 64, 103, "infinite", 56),
        ("inconsistent64", "make_grouped", 32768, 64, 104,
         "inconsistent", 64),
        ("digits", "make_digits", 1797, 61, 105, "unique", 61),
        ("random128", "make_random", 32768, 128, 106, "unique", 128),
        ("grouped256", "make_grouped", 32768, 256, 107, "unique", 256),
        ("rankdef256", "make_random", 16384, 256, 108, "infinite", 240),
        ("random512", "make_random", 4096, 512, 109, "unique", 512),
    )
    for name, generator, m, n, seed, status, rank in standard:
        cases.append(_case(
            f"standard.{name}", "standard", generator, m, n, [seed],
            expected_status=status, expected_rank=rank,
            timings=[_timing("router", "solver-reported", 4, 11),
                     _timing("sequential_reference", "solver-reported", 2, 7)],
            routing_seeds=tuple(range(777, 781)) + tuple(range(877, 888))))

    levels = ("1e-08", "3e-09", "1e-09", "3e-10", "3e-11", "1e-12")
    for index, level in enumerate(levels):
        status, rank, lo, hi = (("unique", 256, 256, 256)
                                if index < 3 else
                                ("undecidable", 255, 255, 256))
        cases.append(_case(
            f"rank.eps_{level}", "rank", "make_rank_transition", 512, 256,
            range(7000, 7020), expected_status=status, expected_rank=rank,
            expected_rank_lo=lo, expected_rank_hi=hi,
            timings=[_timing("router", "solver-reported", 0, 20)],
            routing_seeds=range(8000, 8020)))

    for m, n, rank in ((2000, 64, 63), (10000, 64, 63),
                       (50000, 64, 63), (5000, 96, 95),
                       (20000, 96, 95), (10000, 64, 32),
                       (10000, 64, 1), (512, 192, 191)):
        cases.append(_case(
            f"guard.{m}x{n}.r{rank}", "guard", "make_integer_rank", m, n,
            [12000 + m + n + rank], expected_status="infinite",
            expected_rank=rank,
            timings=[_timing("router", "solver-reported", 3, 9)],
            routing_seeds=tuple(range(777, 780)) + tuple(range(877, 886))))

    scaling = (
        ("grouped64", "make_grouped", 65536, 64, 13000, "unique", 64),
        ("rankdef64", "make_random", 32768, 64, 13001, "infinite", 56),
        ("grouped256", "make_grouped", 32768, 256, 13000, "unique", 256),
    )
    for threads in (1, 2, 4):
        for name, generator, m, n, seed, status, rank in scaling:
            cases.append(_case(
                f"scaling.omp{threads}.{name}", "scaling", generator, m, n,
                [seed], expected_status=status, expected_rank=rank,
                timings=[_timing("router", "solver-reported", 3, 9)],
                routing_seeds=tuple(range(14000, 14003)) +
                              tuple(range(14100, 14109))))

    for n in (32, 64, 128, 256, 512):
        for mult in (4, 16, 64):
            m = n * mult
            for prefix, rank, seed, status in (
                    ("full", n, 20000 + n + mult, "unique"),
                    ("def", n - max(1, n // 8), 21000 + n + mult,
                     "infinite")):
                index = sum(item["section"] == "structural" for item in cases)
                cases.append(_case(
                    f"structural.{prefix}_n{n}_x{mult}", "structural",
                    "make_structured_rank", m, n, [seed],
                    expected_status=status, expected_rank=rank,
                    timings=[_timing("router", "solver-reported", 0, 3)],
                    routing_seeds=[31001 + index * 17,
                                   31002 + index * 17,
                                   31003 + index * 17]))
    for rank in (1, 2, 4, 8, 16, 64):
        index = sum(item["section"] == "structural" for item in cases)
        cases.append(_case(
            f"structural.late_n128_r0_{rank}", "structural",
            "make_late_growth", 4096, 128, [22000 + rank],
            expected_status="unique", expected_rank=128,
            timings=[_timing("router", "solver-reported", 0, 3)],
            routing_seeds=[31001 + index * 17, 31002 + index * 17,
                           31003 + index * 17]))
    for name, m, n, rank, seed in (
            ("delayed_n64", 8192, 64, 64, 23001),
            ("delayed_n128", 8192, 128, 128, 23002)):
        index = sum(item["section"] == "structural" for item in cases)
        cases.append(_case(
            f"structural.{name}", "structural", "make_late_growth", m, n,
            [seed], expected_status="unique", expected_rank=rank,
            timings=[_timing("router", "solver-reported", 0, 3)],
            routing_seeds=[31001 + index * 17, 31002 + index * 17,
                           31003 + index * 17]))
    for n in (64, 128):
        index = sum(item["section"] == "structural" for item in cases)
        cases.append(_case(
            f"structural.inconsistent_n{n}", "structural",
            "make_structured_rank", 4096, n, [24000 + n],
            expected_status="inconsistent", expected_rank=n,
            timings=[_timing("router", "solver-reported", 0, 3)],
            routing_seeds=[31001 + index * 17, 31002 + index * 17,
                           31003 + index * 17]))
    for n, rank in ((64, 64), (64, 56), (128, 128), (128, 112)):
        index = sum(item["section"] == "structural" for item in cases)
        cases.append(_case(
            f"structural.scaled_n{n}_r{rank}", "structural",
            "make_structured_rank_scaled", 4096, n, [25000 + n + rank],
            expected_status="unique" if rank == n else "infinite",
            expected_rank=rank,
            timings=[_timing("router", "solver-reported", 0, 3)],
            routing_seeds=[31001 + index * 17, 31002 + index * 17,
                           31003 + index * 17]))

    lapack = (
        ("random64", "make_random", 32768, 64, 101, "unique", 64),
        ("grouped64", "make_grouped", 65536, 64, 102, "unique", 64),
        ("rankdef64", "make_random", 32768, 64, 103, "infinite", 56),
        ("random128", "make_random", 32768, 128, 106, "unique", 128),
        ("rankdef256", "make_random", 16384, 256, 108, "infinite", 240),
        ("random512", "make_random", 4096, 512, 109, "unique", 512),
    )
    for name, generator, m, n, seed, status, rank in lapack:
        cases.append(_case(
            f"lapack.{name}", "lapack", generator, m, n, [seed],
            expected_status=status, expected_rank=rank,
            timings=[_timing("router", "perf_counter_ns", 2, 7),
                     _timing("dgelsy", "perf_counter_ns", 2, 7)],
            routing_seeds=[47001] * 9))
    return tuple(cases)


_CASES = _build_cases()
CANONICAL_CASES_BY_ID = {item["case_id"]: item for item in _CASES}
CANONICAL_CASE_IDS = {
    section: tuple(item["case_id"] for item in _CASES
                   if item["section"] == section)
    for section, _ in CANONICAL_SECTIONS
}
CANONICAL_PROTOCOL = {
    "protocol_id": PROTOCOL_ID,
    "schema_version": RESULT_SCHEMA_VERSION,
    "sections": [
        {"section_id": section, "output_name": output,
         "cases": [CANONICAL_CASES_BY_ID[case_id]
                   for case_id in CANONICAL_CASE_IDS[section]]}
        for section, output in CANONICAL_SECTIONS],
    "candidate_omp": 4,
    "scaling_openmp_schedule": [1, 2, 4],
}


def canonical_json_bytes(document: Any) -> bytes:
    try:
        text = json.dumps(document, indent=2, sort_keys=True,
                          allow_nan=False, ensure_ascii=False) + "\n"
    except (TypeError, ValueError) as exc:
        raise ValueError(f"document is not strict JSON: {exc}") from exc
    return text.encode("utf-8")


def protocol_signature(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(document)).hexdigest()


PROTOCOL_SIGNATURE = protocol_signature(CANONICAL_PROTOCOL)


def sha256_file(path: os.PathLike[str] | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_hex(value: Any, length: int) -> bool:
    return (isinstance(value, str) and len(value) == length and
            all(character in "0123456789abcdefABCDEF" for character in value))


def _finite_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _append(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def parse_sections(value: str, *, candidate: bool = False) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise ValueError("sections must be a comma-separated string")
    sections = tuple(item.strip() for item in value.split(",") if item.strip())
    canonical = tuple(name for name, _ in CANONICAL_SECTIONS)
    if not sections or len(sections) != len(set(sections)) or any(
            item not in canonical for item in sections):
        raise ValueError("sections contain missing, duplicate, or unknown names")
    positions = [canonical.index(item) for item in sections]
    if positions != sorted(positions):
        raise ValueError("sections are reordered")
    if candidate and sections != canonical:
        raise ValueError("candidate requires the exact ordered six sections")
    return sections


def ensure_abi_arrays(A: np.ndarray, b: np.ndarray, x: np.ndarray) -> None:
    arrays = (("A", A, 2), ("b", b, 1), ("x", x, 1))
    for name, array, ndim in arrays:
        if not isinstance(array, np.ndarray) or array.ndim != ndim:
            raise ValueError(f"{name} must be a {ndim}D ndarray")
        if array.dtype != np.dtype(np.float64) or not array.dtype.isnative:
            raise ValueError(f"{name} must be native float64")
        if not array.flags.c_contiguous:
            raise ValueError(f"{name} must be C-contiguous")
    m, n = A.shape
    if b.shape != (m,) or x.shape != (n,):
        raise ValueError("A, b, and x shapes do not agree")
    if A.strides != (n * 8, 8):
        raise ValueError("A must use dense row-major strides")


def describe_input(A: np.ndarray, b: np.ndarray, x: np.ndarray, *,
                   generator: str, seed: int) -> dict[str, Any]:
    ensure_abi_arrays(A, b, x)
    return {
        "generator": generator, "seed": int(seed),
        "m": int(A.shape[0]), "n": int(A.shape[1]),
        "dtype": "float64", "byte_order": "native",
        "layout": "row-major", "c_contiguous": True,
        "strides": [int(value) for value in A.strides],
        "sha256": {
            "A": hashlib.sha256(A.tobytes(order="C")).hexdigest(),
            "b": hashlib.sha256(b.tobytes(order="C")).hexdigest(),
            "x": hashlib.sha256(x.tobytes(order="C")).hexdigest(),
        },
    }


def timing_record(*, operation: str, source: str, warmups: int,
                  repetitions: int, raw: Sequence[float],
                  unit: str = "seconds") -> dict[str, Any]:
    values = [float(value) for value in raw]
    if not isinstance(warmups, int) or warmups < 0:
        raise ValueError("warmups must be a nonnegative integer")
    if not isinstance(repetitions, int) or repetitions <= 0 or \
            len(values) != repetitions:
        raise ValueError("raw timing count differs from repetitions")
    if any(not math.isfinite(value) or value <= 0.0 for value in values):
        raise ValueError("raw timings must be positive and finite")
    median = float(statistics.median(values))
    mad = float(statistics.median(abs(value - median) for value in values))
    return {"operation": operation, "source": source, "unit": unit,
            "warmups": warmups, "repetitions": repetitions, "raw": values,
            "median": median, "mad": mad}


def ratio_record(*, name: str, numerator_operation: str,
                 denominator_operation: str, numerator: float,
                 denominator: float) -> dict[str, Any]:
    numerator = float(numerator); denominator = float(denominator)
    if not math.isfinite(numerator) or numerator <= 0 or \
            not math.isfinite(denominator) or denominator <= 0:
        raise ValueError("ratio operands must be positive finite timings")
    return {"name": name,
            "direction": f"{numerator_operation}/{denominator_operation}",
            "value": numerator / denominator}


def strict_json_loads(data: str | bytes) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"forbidden JSON constant {value}")
    return json.loads(data, parse_constant=reject_constant)


def _input_reasons(record: Any, spec: Mapping[str, Any],
                   case_id: str) -> list[str]:
    reasons: list[str] = []
    if not isinstance(record, dict):
        return [f"result_input_invalid:{case_id}"]
    if record.get("generator") != spec["generator"]:
        _append(reasons, f"result_input_generator_mismatch:{case_id}")
    if record.get("seed") not in spec["input_seeds"]:
        _append(reasons, f"result_input_seed_mismatch:{case_id}")
    if record.get("m") != spec["m"] or record.get("n") != spec["n"]:
        _append(reasons, f"result_input_shape_mismatch:{case_id}")
    if record.get("dtype") != "float64":
        _append(reasons, f"result_input_dtype_invalid:{case_id}")
    if record.get("byte_order") != "native":
        _append(reasons, f"result_input_byte_order_invalid:{case_id}")
    if record.get("layout") != "row-major" or \
            record.get("c_contiguous") is not True:
        _append(reasons, f"result_input_layout_invalid:{case_id}")
    if record.get("strides") != [spec["n"] * 8, 8]:
        _append(reasons, f"result_input_strides_invalid:{case_id}")
    hashes = record.get("sha256") if isinstance(record.get("sha256"), dict) else {}
    for name in ("A", "b", "x"):
        if not _valid_hex(hashes.get(name), 64):
            _append(reasons, f"result_input_hash_invalid:{case_id}:{name}")
    if case_id == "standard.digits" and \
            hashes.get("A") != DIGITS_DESIGN_SHA256:
        _append(reasons, "result_digits_design_hash_mismatch")
    return reasons


def _timing_reasons(record: Any, expected: Mapping[str, Any],
                    case_id: str) -> list[str]:
    operation = expected["operation"]
    prefix = f"{case_id}:{operation}"
    if not isinstance(record, dict):
        return [f"result_timing_invalid:{prefix}"]
    reasons: list[str] = []
    if record.get("operation") != operation:
        _append(reasons, f"result_timing_operation_mismatch:{prefix}")
    if record.get("source") != expected["source"]:
        _append(reasons, f"result_timing_source_mismatch:{prefix}")
    if record.get("warmups") != expected["warmups"]:
        _append(reasons, f"result_timing_warmups_mismatch:{prefix}")
    if record.get("repetitions") != expected["repetitions"]:
        _append(reasons, f"result_timing_repetitions_mismatch:{prefix}")
    raw = record.get("raw")
    if not isinstance(raw, list) or len(raw) != expected["repetitions"] or \
            any(not _finite_number(value) or value <= 0 for value in raw):
        _append(reasons, f"result_timing_raw_invalid:{prefix}")
        return reasons
    median = float(statistics.median(raw))
    mad = float(statistics.median(abs(value - median) for value in raw))
    if not _finite_number(record.get("median")) or not math.isclose(
            float(record["median"]), median, rel_tol=1e-12, abs_tol=0):
        _append(reasons, f"result_timing_median_mismatch:{prefix}")
    if not _finite_number(record.get("mad")) or not math.isclose(
            float(record["mad"]), mad, rel_tol=1e-12, abs_tol=1e-15):
        _append(reasons, f"result_timing_mad_mismatch:{prefix}")
    return reasons


def validate_result_document(document: Any, *,
                             require_complete: bool = True) -> list[str]:
    reasons: list[str] = []
    if not isinstance(document, dict):
        return ["result_document_invalid"]
    if document.get("schema_version") != RESULT_SCHEMA_VERSION:
        _append(reasons, "result_schema_version_invalid")
    if document.get("protocol_id") != PROTOCOL_ID:
        _append(reasons, "result_protocol_id_invalid")
    signature = document.get("protocol_signature")
    if signature is None:
        _append(reasons, "result_protocol_signature_missing")
    elif signature != PROTOCOL_SIGNATURE:
        _append(reasons, "result_protocol_signature_mismatch")
    sections = document.get("sections")
    if not isinstance(sections, list):
        _append(reasons, "result_sections_invalid")
        _append(reasons, "result_raw_timings_missing")
        return reasons
    section_ids = [item.get("section_id") if isinstance(item, dict) else None
                   for item in sections]
    if any(count > 1 for name, count in Counter(section_ids).items()
           if name is not None):
        _append(reasons, "result_section_duplicate")
    canonical_sections = tuple(name for name, _ in CANONICAL_SECTIONS)
    if require_complete:
        if tuple(section_ids) != canonical_sections:
            _append(reasons, "result_section_order_mismatch")
    else:
        if any(name not in canonical_sections for name in section_ids) or \
                [canonical_sections.index(name) for name in section_ids
                 if name in canonical_sections] != sorted(
                    canonical_sections.index(name) for name in section_ids
                    if name in canonical_sections):
            _append(reasons, "result_section_order_mismatch")

    output_names = dict(CANONICAL_SECTIONS)
    saw_timing = False
    for section in sections:
        if not isinstance(section, dict):
            _append(reasons, "result_section_invalid"); continue
        section_id = section.get("section_id")
        if section_id not in output_names:
            _append(reasons, f"result_section_unknown:{section_id}"); continue
        if section.get("output_name") != output_names[section_id]:
            _append(reasons, f"result_output_name_mismatch:{section_id}")
        cases = section.get("cases")
        if not isinstance(cases, list):
            _append(reasons, f"result_cases_invalid:{section_id}"); continue
        ids = [case.get("case_id") if isinstance(case, dict) else None
               for case in cases]
        for case_id, count in Counter(ids).items():
            if case_id is not None and count > 1:
                _append(reasons, f"result_case_duplicate:{case_id}")
        for case_id in ids:
            if case_id not in CANONICAL_CASES_BY_ID:
                _append(reasons, f"result_case_unknown:{case_id}")
        if tuple(ids) != CANONICAL_CASE_IDS[section_id]:
            _append(reasons, f"result_case_order_mismatch:{section_id}")
        summary = section.get("summary")
        if not isinstance(summary, dict) or summary.get("case_count") != len(cases):
            _append(reasons, f"result_summary_case_count_mismatch:{section_id}")
        timing_by_case = {}
        for case in cases:
            if isinstance(case, dict):
                timing_by_case[case.get("case_id")] = {
                    timing.get("operation"): timing.get("median")
                    for timing in case.get("timings", [])
                    if isinstance(timing, dict)}
        hard_failures = 0
        section_ratios: list[float] = []
        for case in cases:
            if not isinstance(case, dict):
                _append(reasons, f"result_case_invalid:{section_id}"); continue
            case_id = case.get("case_id")
            spec = CANONICAL_CASES_BY_ID.get(case_id)
            if spec is None:
                continue
            inputs = case.get("inputs")
            if not isinstance(inputs, list) or not inputs:
                _append(reasons, f"result_inputs_invalid:{case_id}")
            else:
                seeds = [item.get("seed") if isinstance(item, dict) else None
                         for item in inputs]
                if seeds != spec["input_seeds"]:
                    _append(reasons, f"result_input_seed_order_mismatch:{case_id}")
                for item in inputs:
                    for reason in _input_reasons(item, spec, case_id):
                        _append(reasons, reason)
            timings = case.get("timings")
            if not isinstance(timings, list):
                _append(reasons, f"result_timings_invalid:{case_id}")
                timings = []
            saw_timing = saw_timing or bool(timings)
            if len(timings) != len(spec["timings"]):
                _append(reasons, f"result_timing_operation_count_mismatch:{case_id}")
            for item, expected in zip(timings, spec["timings"]):
                for reason in _timing_reasons(item, expected, case_id):
                    _append(reasons, reason)
            medians = {item.get("operation"): item.get("median")
                       for item in timings if isinstance(item, dict)}
            ratios = case.get("ratios", [])
            if not isinstance(ratios, list):
                _append(reasons, f"result_ratios_invalid:{case_id}"); ratios = []
            standard_directions = {
                "sequential_reference_over_router":
                    ("sequential_reference", "router"),
                "dgelsy_over_router": ("dgelsy", "router"),
            }
            for ratio in ratios:
                if not isinstance(ratio, dict):
                    _append(reasons, f"result_ratio_invalid:{case_id}"); continue
                if ratio.get("name") == "one_thread_router_over_router":
                    if ratio.get("direction") != "omp1_router/router":
                        _append(reasons, f"result_ratio_direction_mismatch:{case_id}")
                    numerator = timing_by_case.get(
                        ratio.get("numerator_case_id"), {}).get("router")
                    denominator = timing_by_case.get(
                        ratio.get("denominator_case_id"), {}).get("router")
                else:
                    operations = standard_directions.get(ratio.get("name"))
                    if operations is None:
                        _append(reasons, f"result_ratio_name_invalid:{case_id}")
                        continue
                    numerator_name, denominator_name = operations
                    if ratio.get("direction") != f"{numerator_name}/{denominator_name}":
                        _append(reasons, f"result_ratio_direction_mismatch:{case_id}")
                    numerator = medians.get(numerator_name)
                    denominator = medians.get(denominator_name)
                expected_value = (numerator / denominator
                                  if _finite_number(numerator) and
                                  _finite_number(denominator) and
                                  denominator > 0 else None)
                if expected_value is None or not _finite_number(ratio.get("value")) \
                        or not math.isclose(float(ratio["value"]), expected_value,
                                            rel_tol=1e-12, abs_tol=0):
                    _append(reasons, f"result_ratio_value_mismatch:{case_id}")
                else:
                    section_ratios.append(expected_value)
            runs = case.get("runs")
            if runs is not None:
                if not isinstance(runs, list) or not runs:
                    _append(reasons, f"result_runs_invalid:{case_id}")
                else:
                    run_ids = []
                    for run in runs:
                        if not isinstance(run, dict) or run.get("case_id") != case_id \
                                or not isinstance(run.get("run_id"), str) \
                                or not run.get("run_id"):
                            _append(reasons, f"result_run_identity_invalid:{case_id}")
                        else:
                            run_ids.append(run["run_id"])
                    if len(run_ids) != len(set(run_ids)):
                        _append(reasons, f"result_run_identity_duplicate:{case_id}")
            numerical = case.get("numerical_contract")
            if not isinstance(numerical, dict) or numerical.get("valid") is not True \
                    or not isinstance(numerical.get("reasons"), list):
                _append(reasons, f"result_numerical_contract_invalid:{case_id}")
                hard_failures += 1
            elif numerical["reasons"]:
                _append(reasons, f"result_numerical_contract_inconsistent:{case_id}")
            expected = numerical.get("expected") if isinstance(numerical, dict) else None
            if not isinstance(expected, dict) or \
                    expected.get("status") != spec["expected_status"] or \
                    expected.get("rank") != spec["expected_rank"]:
                _append(reasons, f"result_numerical_expected_mismatch:{case_id}")
            if section_id == "rank" and isinstance(expected, dict) and \
                    expected.get("rank_interval") != [spec["expected_rank_lo"],
                                                       spec["expected_rank_hi"]]:
                _append(reasons, f"result_numerical_expected_interval_mismatch:{case_id}")
            actual = numerical.get("actual") if isinstance(numerical, dict) else None
            if not isinstance(actual, dict) or \
                    actual.get("status") != spec["expected_status"] or \
                    (spec["expected_status"] != "inconsistent" and
                     actual.get("rank") != spec["expected_rank"]):
                _append(reasons, f"result_numerical_outcome_mismatch:{case_id}")
            diagnostics = case.get("diagnostics")
            if not isinstance(diagnostics, dict):
                _append(reasons, f"result_diagnostics_invalid:{case_id}")
            else:
                rank = diagnostics.get("rank")
                lo = diagnostics.get("rank_lo")
                hi = diagnostics.get("rank_hi")
                if not isinstance(diagnostics.get("status"), str) or not all(
                        isinstance(value, int) and not isinstance(value, bool)
                        for value in (rank, lo, hi)):
                    _append(reasons, f"result_diagnostics_fields_invalid:{case_id}")
                elif not lo <= rank <= hi:
                    _append(reasons, f"result_rank_interval_invalid:{case_id}")
                if section_id == "rank" and \
                        diagnostics.get("finite_residual_count") == 0 and \
                        diagnostics.get("router_relres") is not None:
                    _append(reasons, "result_transition_unavailable_residual_not_null")
                if isinstance(actual, dict) and all(
                        key in actual for key in ("status", "rank")) and (
                            actual.get("status") != diagnostics.get("status") or
                            actual.get("rank") != diagnostics.get("rank")):
                    _append(reasons,
                            f"result_numerical_actual_diagnostics_mismatch:{case_id}")
        if section_id == "structural" and isinstance(summary, dict):
            if summary.get("hard_failure_count") != hard_failures or \
                    summary.get("reported_hard_failure_count") != hard_failures:
                _append(reasons, "result_structural_hard_failure_count_mismatch")
        if isinstance(summary, dict) and (
                "ratio_count" in summary or "ratio_geomean" in summary):
            count = len(section_ratios)
            geomean = (math.exp(statistics.mean(math.log(value)
                                               for value in section_ratios))
                       if section_ratios else None)
            if summary.get("ratio_count") != count or geomean is None or \
                    not _finite_number(summary.get("ratio_geomean")) or \
                    not math.isclose(float(summary["ratio_geomean"]), geomean,
                                     rel_tol=1e-12, abs_tol=0):
                _append(reasons,
                        f"result_summary_ratio_aggregate_mismatch:{section_id}")
    if not saw_timing:
        _append(reasons, "result_raw_timings_missing")
    top = document.get("numerical_contract")
    if not isinstance(top, dict) or top.get("valid") is not True:
        _append(reasons, "result_numerical_contract_invalid")
    return reasons


_PRIVATE_KEYS = frozenset((
    "hostname", "username", "user_name", "serial", "serial_number", "mac",
    "mac_address", "token", "access_token", "credential", "credentials",
    "password", "secret"))


def _contains_private_or_absolute(value: Any, key: str = "") -> bool:
    if key.lower() in _PRIVATE_KEYS:
        return True
    if isinstance(value, dict):
        return any(_contains_private_or_absolute(item, str(name))
                   for name, item in value.items())
    if isinstance(value, list):
        return any(_contains_private_or_absolute(item, key) for item in value)
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        if normalized.startswith(("~", "file://", "/home/", "/Users/",
                                  "/projects/", "/workspace/")):
            return True
        if any(marker in normalized
               for marker in ("/.venv/", "/venv/", "/virtualenv/")):
            return True
    return False


def _relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in ("", ".", "..")
                                          for part in path.parts)


def _source_reasons(state: Any, label: str) -> list[str]:
    if not isinstance(state, dict):
        return [f"source_{label}_invalid"]
    reasons = []
    if not _valid_hex(state.get("git_sha"), 40):
        _append(reasons, f"source_{label}_sha_invalid")
    if not _valid_hex(state.get("git_tree_sha"), 40):
        _append(reasons, f"source_{label}_tree_invalid")
    if state.get("git_dirty") is not False:
        _append(reasons, f"source_{label}_dirty")
    return reasons


def validate_metadata_document(document: Any, *,
                               result_bytes: bytes | None = None) -> list[str]:
    if not isinstance(document, dict):
        return ["metadata_document_invalid"]
    reasons: list[str] = []
    if document.get("schema_version") != METADATA_SCHEMA_VERSION:
        _append(reasons, "metadata_schema_version_invalid")
    if document.get("scope") != "reference-machine-numerical-evidence":
        _append(reasons, "metadata_scope_invalid")
    if not isinstance(document.get("reference_machine_id"), str) or \
            not document.get("reference_machine_id"):
        _append(reasons, "reference_machine_id_missing")
    result = document.get("result") if isinstance(document.get("result"), dict) else {}
    if result.get("filename") != RESULT_FILENAME:
        _append(reasons, "metadata_result_filename_invalid")
    if result_bytes is not None:
        if result.get("sha256") != hashlib.sha256(result_bytes).hexdigest():
            _append(reasons, "result_hash_mismatch")
    elif not _valid_hex(result.get("sha256"), 64):
        _append(reasons, "result_hash_invalid")
    if result.get("schema_version") != RESULT_SCHEMA_VERSION:
        _append(reasons, "metadata_result_schema_mismatch")
    if result.get("protocol_id") != PROTOCOL_ID:
        _append(reasons, "metadata_protocol_id_mismatch")
    if result.get("protocol_signature") != PROTOCOL_SIGNATURE:
        _append(reasons, "metadata_protocol_signature_mismatch")
    source = document.get("source") if isinstance(document.get("source"), dict) else {}
    before, after = source.get("before"), source.get("after")
    for reason in _source_reasons(before, "before") + _source_reasons(after, "after"):
        _append(reasons, reason)
    if isinstance(before, dict) and isinstance(after, dict) and before != after:
        _append(reasons, "source_state_changed")
    generator = document.get("generator")
    if not isinstance(generator, dict) or not _relative_path(generator.get("path")) \
            or not _valid_hex(generator.get("sha256"), 64):
        _append(reasons, "generator_identity_incomplete")
    locks = document.get("dependency_locks")
    expected_locks = {"requirements-numerical-suite.txt", "requirements-ci.txt"}
    if not isinstance(locks, list) or {
            item.get("path") for item in locks if isinstance(item, dict)
            and _relative_path(item.get("path"))
            and _valid_hex(item.get("sha256"), 64)} != expected_locks:
        _append(reasons, "dependency_lock_identity_incomplete")
    command = document.get("command")
    if not isinstance(command, dict) or not isinstance(command.get("argv"), list) \
            or not command.get("argv"):
        _append(reasons, "command_argv_missing")
    if not isinstance(command, dict) or not isinstance(
            command.get("executable_basename"), str) or \
            not command.get("executable_basename") or \
            Path(command["executable_basename"]).name != command["executable_basename"]:
        _append(reasons, "command_executable_missing")
    run = document.get("run")
    if not isinstance(run, dict) or not run.get("started_utc") or \
            not run.get("ended_utc") or not _finite_number(
                run.get("duration_seconds")) or run.get("duration_seconds", -1) < 0:
        _append(reasons, "run_timing_identity_incomplete")
    build = document.get("build") if isinstance(document.get("build"), dict) else {}
    if not _valid_hex(build.get("manifest_sha256"), 64):
        _append(reasons, "build_manifest_hash_invalid")
    if not build.get("built_at_utc"):
        _append(reasons, "build_timestamp_missing")
    build_source = build.get("source") if isinstance(build.get("source"), dict) else {}
    if isinstance(before, dict):
        if build_source.get("git_sha") != before.get("git_sha"):
            _append(reasons, "build_source_sha_mismatch")
        if build_source.get("git_tree_sha") != before.get("git_tree_sha"):
            _append(reasons, "build_source_tree_mismatch")
    if build_source.get("git_dirty") is not False:
        _append(reasons, "build_source_dirty")
    script = build.get("build_script") if isinstance(build.get("build_script"), dict) else {}
    if script.get("path") != "build.sh" or not _valid_hex(script.get("sha256"), 64):
        _append(reasons, "build_script_hash_invalid")
    compiler = build.get("compiler") if isinstance(build.get("compiler"), dict) else {}
    if not compiler.get("identity"):
        _append(reasons, "compiler_identity_missing")
    if not isinstance(compiler.get("command_argv"), list) or not compiler.get("command_argv"):
        _append(reasons, "compiler_argv_missing")
    router = build.get("router") if isinstance(build.get("router"), dict) else {}
    if router.get("basename") != ROUTER_BASENAME:
        _append(reasons, "router_basename_mismatch")
    if not _valid_hex(router.get("sha256"), 64):
        _append(reasons, "router_hash_invalid")
    for name in ("compile_argv", "link_argv"):
        if not isinstance(router.get(name), list) or not router.get(name):
            _append(reasons, f"router_{name}_missing")
    linked = build.get("linked_blas") if isinstance(build.get("linked_blas"), dict) else {}
    if not linked.get("basename"):
        _append(reasons, "linked_blas_basename_missing")
    if not _valid_hex(linked.get("sha256"), 64):
        _append(reasons, "linked_blas_hash_invalid")
    runtime = document.get("runtime") if isinstance(document.get("runtime"), dict) else {}
    loaded = runtime.get("loaded_router") if isinstance(runtime.get("loaded_router"), dict) else {}
    if loaded.get("basename") != router.get("basename"):
        _append(reasons, "runtime_router_basename_mismatch")
    if loaded.get("sha256") != router.get("sha256"):
        _append(reasons, "runtime_router_hash_mismatch")
    pools = runtime.get("blas_pools")
    if not isinstance(pools, list) or not pools:
        _append(reasons, "runtime_blas_pool_missing"); pools = []
    runtime_hashes = set()
    for pool in pools:
        if not isinstance(pool, dict) or not pool.get("basename") or \
                not _valid_hex(pool.get("sha256"), 64):
            _append(reasons, "runtime_blas_pool_identity_incomplete"); continue
        runtime_hashes.add(pool["sha256"])
        if pool.get("num_threads") != 1:
            _append(reasons,
                    f"runtime_blas_not_single_threaded:{pool.get('basename')}")
    if _valid_hex(linked.get("sha256"), 64) and \
            linked.get("sha256") not in runtime_hashes:
        _append(reasons, "runtime_linked_blas_hash_mismatch")
    controls = runtime.get("thread_controls") if isinstance(
        runtime.get("thread_controls"), dict) else {}
    if controls.get("OMP_NUM_THREADS") != "4":
        _append(reasons, "thread_control_invalid:OMP_NUM_THREADS")
    for name in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                 "VECLIB_MAXIMUM_THREADS"):
        if controls.get(name) != "1":
            _append(reasons, f"thread_control_not_one:{name}")
    if runtime.get("openmp_schedule") != [1, 2, 4]:
        _append(reasons, "openmp_schedule_mismatch")
    machine = document.get("machine") if isinstance(document.get("machine"), dict) else {}
    for name in ("cpu_model", "physical_cores", "logical_cores", "ram_bytes",
                 "os", "kernel"):
        if machine.get(name) in (None, "", 0):
            _append(reasons, f"machine_identity_missing:{name}")
    software = document.get("software") if isinstance(document.get("software"), dict) else {}
    for name in ("python", "numpy", "scipy", "scikit-learn", "threadpoolctl",
                 "mpmath", "joblib", "cloudpickle", "narwhals"):
        if not software.get(name):
            _append(reasons, f"software_identity_missing:{name}")
    eligibility = document.get("evidence_eligibility")
    if not isinstance(eligibility, dict) or not isinstance(
            eligibility.get("eligible"), bool) or not isinstance(
                eligibility.get("reasons"), list):
        _append(reasons, "metadata_eligibility_invalid")
    elif eligibility["eligible"] == bool(eligibility["reasons"]):
        _append(reasons, "metadata_eligibility_inconsistent")
    if _contains_private_or_absolute(document):
        _append(reasons, "metadata_private_or_absolute_value")
    return reasons


def evaluate_eligibility(*, result: Mapping[str, Any],
                         metadata: Mapping[str, Any], candidate: bool,
                         omp: int) -> dict[str, Any]:
    reasons: list[str] = []
    actual_sections = [item.get("section_id")
                       for item in result.get("sections", [])
                       if isinstance(item, dict)]
    if actual_sections != [name for name, _ in CANONICAL_SECTIONS]:
        _append(reasons, "partial_diagnostic_run")
    if not candidate:
        _append(reasons, "candidate_mode_not_requested")
    if omp != 4:
        _append(reasons, "candidate_omp_must_equal_4")
    for reason in validate_result_document(result):
        _append(reasons, reason)
    result_bytes = canonical_json_bytes(result)
    for reason in validate_metadata_document(metadata, result_bytes=result_bytes):
        _append(reasons, reason)
    return {"eligible": not reasons, "reasons": reasons}


def verify_build_manifest(*, router_path: os.PathLike[str] | str,
                          manifest_path: os.PathLike[str] | str,
                          build_script_path: os.PathLike[str] | str,
                          source_state: Mapping[str, Any]) -> dict[str, Any]:
    router_path = Path(router_path).resolve()
    manifest_path = Path(manifest_path).resolve()
    build_script_path = Path(build_script_path).resolve()
    reasons: list[str] = []
    result = {"verified": False, "reasons": reasons, "manifest": None,
              "router_sha256": None, "manifest_sha256": None}
    if manifest_path.parent != router_path.parent:
        _append(reasons, "build_manifest_not_adjacent")
    try:
        result["router_sha256"] = sha256_file(router_path)
    except OSError:
        _append(reasons, "router_library_unreadable")
    if not manifest_path.is_file():
        _append(reasons, "build_manifest_missing"); return result
    try:
        raw = manifest_path.read_bytes()
        result["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
        manifest = strict_json_loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        _append(reasons, "build_manifest_invalid_json"); return result
    result["manifest"] = manifest
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        _append(reasons, "build_manifest_schema_invalid"); return result
    if not manifest.get("built_at_utc"):
        _append(reasons, "build_timestamp_missing")
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    if source.get("git_sha") != source_state.get("git_sha"):
        _append(reasons, "build_source_sha_mismatch")
    if source.get("git_tree_sha") != source_state.get("git_tree_sha"):
        _append(reasons, "build_source_tree_mismatch")
    if source.get("git_dirty") is not False:
        _append(reasons, "build_source_dirty")
    script = manifest.get("build_script") if isinstance(manifest.get("build_script"), dict) else {}
    try:
        script_hash = sha256_file(build_script_path)
    except OSError:
        script_hash = None
    if script.get("sha256") != script_hash:
        _append(reasons, "build_script_hash_mismatch")
    compiler = manifest.get("compiler") if isinstance(manifest.get("compiler"), dict) else {}
    if not compiler.get("identity"):
        _append(reasons, "build_compiler_identity_missing")
    compiler_argv = compiler.get("command_argv")
    if not isinstance(compiler_argv, list) or not compiler_argv:
        _append(reasons, "build_compiler_command_missing")
    router = manifest.get("router") if isinstance(manifest.get("router"), dict) else {}
    compile_argv = router.get("compile_argv"); link_argv = router.get("link_argv")
    if isinstance(compiler_argv, list) and compiler_argv:
        if not isinstance(compile_argv, list) or \
                compile_argv[:len(compiler_argv)] != compiler_argv:
            _append(reasons, "router_compile_compiler_mismatch")
        if not isinstance(link_argv, list) or \
                link_argv[:len(compiler_argv)] != compiler_argv:
            _append(reasons, "router_link_compiler_mismatch")
    for name, value in (("compile_argv", compile_argv), ("link_argv", link_argv)):
        if not isinstance(value, list) or not value:
            _append(reasons, f"router_{name}_missing")
    library = router.get("library") if isinstance(router.get("library"), dict) else {}
    if library.get("basename") != router_path.name:
        _append(reasons, "router_library_basename_mismatch")
    try:
        same_path = Path(library.get("resolved_path")).resolve() == router_path
    except (TypeError, ValueError, OSError):
        same_path = False
    if not same_path:
        _append(reasons, "router_library_path_mismatch")
    if result["router_sha256"] is not None and \
            library.get("sha256") != result["router_sha256"]:
        _append(reasons, "router_library_hash_mismatch")
    linked = manifest.get("openblas") if isinstance(manifest.get("openblas"), dict) else {}
    linked_path = linked.get("resolved_path")
    if not linked.get("basename") or not _valid_hex(linked.get("sha256"), 64):
        _append(reasons, "linked_blas_identity_missing")
    else:
        try:
            if Path(linked_path).name != linked["basename"]:
                _append(reasons, "linked_blas_basename_mismatch")
            if sha256_file(linked_path) != linked["sha256"]:
                _append(reasons, "linked_blas_hash_mismatch")
        except (TypeError, OSError):
            _append(reasons, "linked_blas_unreadable")
        if isinstance(link_argv, list) and linked_path not in link_argv:
            _append(reasons, "linked_blas_argv_mismatch")
    result["verified"] = not reasons
    return result


def _configure_router_handle(handle: Any) -> None:
    pointer = ctypes.POINTER(ctypes.c_double)
    handle.bsolve_router_meta_api.argtypes = [
        pointer, pointer, pointer, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_ulonglong, ctypes.c_int, pointer]
    handle.bsolve_router_meta_api.restype = None
    handle.bsolve_seq_api.argtypes = [pointer, pointer, pointer,
                                     ctypes.c_int, ctypes.c_int, pointer]
    handle.bsolve_seq_api.restype = None
    handle.bsolve_lapack_api.argtypes = [pointer, pointer, pointer,
                                        ctypes.c_int, ctypes.c_int, pointer]
    handle.bsolve_lapack_api.restype = None
    handle.bsolve_fg_counters_reset_api.argtypes = []
    handle.bsolve_fg_counters_reset_api.restype = None
    handle.bsolve_fg_counters_api.argtypes = [ctypes.POINTER(ctypes.c_ulonglong)]
    handle.bsolve_fg_counters_api.restype = None


def resolve_and_load_router(*, root: os.PathLike[str] | str,
                            source_state: Mapping[str, Any],
                            lib_dir: os.PathLike[str] | str | None = None,
                            cdll: Any = ctypes.CDLL,
                            build_script_path: os.PathLike[str] | str | None = None
                            ) -> tuple[Any, dict[str, Any]]:
    root = Path(root).resolve()
    selected_dir = Path(lib_dir or os.environ.get("ABS_LIB_DIR", root)).resolve()
    router_path = (selected_dir / ROUTER_BASENAME).resolve()
    manifest_path = selected_dir / BUILD_MANIFEST_NAME
    evidence = verify_build_manifest(
        router_path=router_path, manifest_path=manifest_path,
        build_script_path=build_script_path or root / "build.sh",
        source_state=source_state)
    if not evidence["verified"]:
        raise RuntimeError("router/build provenance invalid: " +
                           ",".join(evidence["reasons"]))
    handle = cdll(str(router_path))
    _configure_router_handle(handle)
    evidence["router_path"] = str(router_path)
    evidence["manifest_path"] = str(manifest_path.resolve())
    return handle, evidence


def _checksum_entries(text: str) -> tuple[dict[str, str], list[str]]:
    entries: dict[str, str] = {}; reasons: list[str] = []
    for line in text.splitlines():
        parts = line.split("  ", 1)
        if len(parts) != 2 or not _valid_hex(parts[0], 64) or \
                parts[1] not in (RESULT_FILENAME, METADATA_FILENAME) or \
                parts[1] in entries:
            _append(reasons, "package_checksum_invalid"); continue
        entries[parts[1]] = parts[0]
    if tuple(entries) != (RESULT_FILENAME, METADATA_FILENAME):
        _append(reasons, "package_checksum_entries_invalid")
    return entries, reasons


def audit_package(root: os.PathLike[str] | str) -> dict[str, Any]:
    root = Path(root)
    result_path = root / RESULT_FILENAME
    metadata_path = root / METADATA_FILENAME
    checksum_path = root / CHECKSUM_FILENAME
    integrity: list[str] = []
    for path, reason in ((result_path, "package_result_missing"),
                         (metadata_path, "package_metadata_missing"),
                         (checksum_path, "package_checksum_missing")):
        if not path.is_file():
            _append(integrity, reason)
    legacy_path = root / "numerical_final_suite.json"
    if not result_path.is_file() and legacy_path.is_file():
        try:
            legacy = strict_json_loads(legacy_path.read_bytes())
            for reason in validate_result_document(legacy):
                _append(integrity, reason)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            _append(integrity, "legacy_result_json_invalid")
        _append(integrity, "legacy_result_provenance_missing")
    result_bytes = metadata_bytes = None
    result_document = metadata_document = None
    if result_path.is_file():
        try:
            result_bytes = result_path.read_bytes()
            result_document = strict_json_loads(result_bytes)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            _append(integrity, "package_result_json_invalid")
    if metadata_path.is_file():
        try:
            metadata_bytes = metadata_path.read_bytes()
            metadata_document = strict_json_loads(metadata_bytes)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            _append(integrity, "package_metadata_json_invalid")
    entries = {}
    if checksum_path.is_file():
        try:
            entries, checksum_reasons = _checksum_entries(checksum_path.read_text())
            for reason in checksum_reasons:
                _append(integrity, reason)
        except (OSError, UnicodeError):
            _append(integrity, "package_checksum_invalid")
    if result_bytes is not None and entries.get(RESULT_FILENAME) != \
            hashlib.sha256(result_bytes).hexdigest():
        _append(integrity, "package_result_checksum_mismatch")
    if metadata_bytes is not None and entries.get(METADATA_FILENAME) != \
            hashlib.sha256(metadata_bytes).hexdigest():
        _append(integrity, "package_metadata_checksum_mismatch")
    result_reasons = (validate_result_document(result_document)
                      if result_document is not None else
                      ["result_document_unavailable"])
    metadata_reasons = (validate_metadata_document(
        metadata_document, result_bytes=result_bytes)
        if metadata_document is not None else ["metadata_document_unavailable"])
    eligibility_reasons: list[str] = []
    if result_document is not None and metadata_document is not None:
        for reason in result_reasons + metadata_reasons:
            _append(eligibility_reasons, reason)
        verdict = metadata_document.get("evidence_eligibility")
        if not isinstance(verdict, dict) or verdict.get("eligible") is not True:
            _append(eligibility_reasons, "metadata_declares_ineligible")
    else:
        _append(eligibility_reasons, "package_incomplete")
    return {
        "artifact_integrity": {"valid": not integrity, "reasons": integrity},
        "source_build_runtime_provenance": {
            "valid": not metadata_reasons, "reasons": metadata_reasons},
        "protocol_eligibility": {
            "eligible": not eligibility_reasons,
            "reasons": eligibility_reasons},
        "numerical_contract_validity": {
            "valid": not result_reasons, "reasons": result_reasons},
    }


def copy_document(document: Mapping[str, Any]) -> dict[str, Any]:
    return strict_json_loads(canonical_json_bytes(document))


def publish_package_atomic(*, result: Mapping[str, Any],
                           metadata: Mapping[str, Any],
                           result_path: os.PathLike[str] | str,
                           metadata_path: os.PathLike[str] | str,
                           checksum_path: os.PathLike[str] | str) -> None:
    result_path = Path(result_path); metadata_path = Path(metadata_path)
    checksum_path = Path(checksum_path)
    if result_path.name != RESULT_FILENAME or metadata_path.name != METADATA_FILENAME \
            or checksum_path.name != CHECKSUM_FILENAME:
        raise ValueError("candidate outputs must use canonical basenames")
    if len({result_path.parent.resolve(), metadata_path.parent.resolve(),
            checksum_path.parent.resolve()}) != 1:
        raise ValueError("candidate outputs must share one directory")
    result_bytes = canonical_json_bytes(result)
    result_reasons = validate_result_document(result)
    if result_reasons:
        raise ValueError("invalid result: " + ",".join(result_reasons))
    metadata_copy = copy_document(metadata)
    result_record = metadata_copy.setdefault("result", {})
    result_record.update({
        "filename": RESULT_FILENAME,
        "sha256": hashlib.sha256(result_bytes).hexdigest(),
        "schema_version": RESULT_SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "protocol_signature": PROTOCOL_SIGNATURE})
    metadata_bytes = canonical_json_bytes(metadata_copy)
    metadata_reasons = validate_metadata_document(
        metadata_copy, result_bytes=result_bytes)
    if metadata_reasons:
        raise ValueError("invalid metadata: " + ",".join(metadata_reasons))
    checksum_bytes = (
        f"{hashlib.sha256(result_bytes).hexdigest()}  {RESULT_FILENAME}\n"
        f"{hashlib.sha256(metadata_bytes).hexdigest()}  {METADATA_FILENAME}\n"
    ).encode("ascii")
    parent = result_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporaries = []
    try:
        for destination, payload in ((result_path, result_bytes),
                                     (metadata_path, metadata_bytes),
                                     (checksum_path, checksum_bytes)):
            descriptor, name = tempfile.mkstemp(
                prefix=f".{destination.name}.tmp.", dir=parent)
            temporary = Path(name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload); stream.flush(); os.fsync(stream.fileno())
            temporaries.append((temporary, destination))
        for temporary, destination in temporaries:
            os.replace(temporary, destination)
    finally:
        for temporary, _ in temporaries:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def sanitize_threadpools(
        pools: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    sanitized = []
    for pool in pools:
        filepath = pool.get("filepath")
        basename = Path(filepath).name if filepath else pool.get("basename")
        digest = None
        if filepath:
            try:
                digest = sha256_file(filepath)
            except OSError:
                pass
        sanitized.append({
            "user_api": pool.get("user_api"),
            "internal_api": pool.get("internal_api"),
            "num_threads": pool.get("num_threads"),
            "version": pool.get("version"), "basename": basename,
            "sha256": digest or pool.get("sha256")})
    return sanitized


def sanitized_build_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    manifest = evidence.get("manifest") if isinstance(
        evidence.get("manifest"), dict) else {}
    router = manifest.get("router") if isinstance(manifest.get("router"), dict) else {}
    library = router.get("library") if isinstance(router.get("library"), dict) else {}
    linked = manifest.get("openblas") if isinstance(manifest.get("openblas"), dict) else {}
    return {
        "manifest_schema_version": manifest.get("schema_version"),
        "manifest_sha256": evidence.get("manifest_sha256"),
        "built_at_utc": manifest.get("built_at_utc"),
        "source": manifest.get("source"),
        "build_script": manifest.get("build_script"),
        "compiler": manifest.get("compiler"),
        "router": {
            "basename": library.get("basename"),
            "sha256": evidence.get("router_sha256"),
            "compile_argv": router.get("compile_argv"),
            "link_argv": [Path(value).name
                          if isinstance(value, str) and value.startswith("/")
                          else value for value in router.get("link_argv", [])],
            "arch_flags": router.get("arch_flags")},
        "linked_blas": {"basename": linked.get("basename"),
                        "sha256": linked.get("sha256")},
    }
