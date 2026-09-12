#!/usr/bin/env python3
"""
check_paper_claims.py -- assert that the manuscript's quantitative claims are
still reproduced by the current code.

Ordinary regression tests answer "did anything crash".  This script answers a
different and, for a paper artifact, more important question: do the specific
numbers printed in the manuscript still come out of this build?

It runs the two property batteries, parses their JSON, and compares against
the values stated in paper.tex.  A mismatch is a failure even when every
individual test passes, because a silently changed count invalidates a
sentence in the paper.

Exit status: 0 = all claims reproduced, 1 = at least one mismatch.

Usage:
    python3 tests/check_paper_claims.py            # run batteries, compare
    python3 tests/check_paper_claims.py --list     # print expectations only
    python3 tests/check_paper_claims.py --check-performance-inventory
    python3 tests/check_paper_claims.py --audit-performance-artifacts ROOT
    python3 tests/check_paper_claims.py --audit-performance-artifacts ROOT \
        --require-publication-ready
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TESTS = ROOT / "tests"
PERFORMANCE_CLAIM_REGISTRY = ROOT / "experiments" / \
    "manuscript_performance_claims.json"

EVIDENCE_CLASSES = frozenset((
    "current-artifact", "historical-confirmed", "historical-unconfirmed",
    "different-task", "different-generator", "not-covered"))
REQUIRED_PERFORMANCE_CLAIM_IDS = frozenset((
    "audit.certified_call_overhead", "standard.sequential_reference",
    "parallel.openmp_scaling", "structural.stress_timings",
    "transition.rank_gate", "guard.rank1_cost", "well1033.performance",
    "contextual.dgelsy", "wide_extreme.32x12800",
    "wide_extreme.lp_fit2d", "grouped.dgelsy", "grouped.lsmr",
    "limitations.square_underdetermined", "scope.tall_directional",
    "applications.radio_timings", "applications.harmonic_timings",
    "applications.lens_timings",
    "parallel.bundle_tree_late_growth",
    "methodology.quantitative_results_freshness",
    "methodology.json_environment_raw_outputs"))
EXPECTED_RATIO_DIRECTIONS = {
    "audit.certified_call_overhead": "strengthened_audit_over_preceding_audit",
    "standard.sequential_reference": "sequential_reference_over_router",
    "parallel.openmp_scaling": "one_thread_over_multi_thread",
    "structural.stress_timings": "not_a_timing_ratio",
    "transition.rank_gate": "not_a_timing_ratio",
    "guard.rank1_cost": "absolute_router_time",
    "well1033.performance": "dgelsy_over_router",
    "contextual.dgelsy": "dgelsy_over_router",
    "wide_extreme.32x12800": "dgelsy_over_router",
    "wide_extreme.lp_fit2d": "dgelsy_over_router",
    "grouped.dgelsy": "dgelsy_over_router",
    "grouped.lsmr": "lsmr_over_router",
    "limitations.square_underdetermined": "router_over_lapack",
    "scope.tall_directional": "dgelsy_over_router",
    "applications.radio_timings": "dgelsy_over_router",
    "applications.harmonic_timings": "baseline_over_router",
    "applications.lens_timings": "baseline_over_router",
    "parallel.bundle_tree_late_growth": "tree_over_sequential_bundle",
    "methodology.quantitative_results_freshness": "not_a_timing_ratio",
    "methodology.json_environment_raw_outputs": "not_a_timing_ratio",
}
EXPECTED_ARTIFACT_CASE_MAPPINGS = {
    "transition.rank_gate": (
        "near_transition.eps_1e-12", "near_transition.eps_1e-10"),
    "wide_extreme.32x12800": ("wide_extreme.32x12800",),
    "grouped.dgelsy": (
        "grouped_vs_lapack.16384x64",
        "grouped_vs_lapack.131072x64",
        "grouped_vs_lapack.16384x256"),
    "grouped.lsmr": (
        "grouped_vs_lsmr.16384x64",
        "grouped_vs_lsmr.131072x64",
        "grouped_vs_lsmr.16384x256"),
    "limitations.square_underdetermined": (
        "square.256x256", "square.512x512", "wide.128x512",
        "wide.256x2048", "wide_large.2000x8000"),
    "scope.tall_directional": (
        "tall.8000x32", "tall.7680x64", "tall.7680x128",
        "tall_large.8000x2000", "tall_large.20000x2000"),
}
CLAIM_REQUIRED_FIELDS = (
    "claim_id", "manuscript_anchor", "text_anchor", "numerator",
    "denominator", "ratio_direction", "dimensions_case_identity",
    "baseline_driver", "generator_dataset", "task_relationship",
    "evidence_class", "artifact_case_mapping", "historical_source_identity",
    "machine_protocol_scope", "publication_status")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_hex(value, length):
    return (isinstance(value, str) and len(value) == length and
            all(character in "0123456789abcdefABCDEF" for character in value))


def _finite_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool) and
            math.isfinite(value))


def _safe_git_path(value):
    if not isinstance(value, str) or not value or "\\" in value or \
            ":" in value or any(unicodedata.category(character) == "Cc"
                                for character in value):
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..")
                                 for part in path.parts):
        return None
    return str(path)


def _git_output(repo_root, *arguments):
    try:
        completed = subprocess.run(
            ["git", *arguments], cwd=repo_root, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, check=False)
    except (OSError, ValueError):
        return None
    return completed.stdout if completed.returncode == 0 else None


def _git_commit_tree(commit, repo_root=ROOT):
    if not _valid_hex(commit, 40):
        return None
    object_type = _git_output(repo_root, "cat-file", "-t", commit)
    if object_type is None or object_type.decode().strip() != "commit":
        return None
    output = _git_output(repo_root, "rev-parse", "--verify",
                         f"{commit}^{{tree}}")
    return output.decode().strip() if output is not None else None


def load_performance_claim_registry(path=PERFORMANCE_CLAIM_REGISTRY):
    """Load the bounded explicit registry; callers may safely mutate it."""
    return json.loads(Path(path).read_text())


def validate_performance_claim_registry(registry, manuscript_text=None):
    """Return every inventory/schema error using stable reason codes."""
    reasons = []
    if not isinstance(registry, dict) or registry.get("schema_version") != 1:
        return ["claim_registry_schema_invalid"]
    claims = registry.get("claims")
    if not isinstance(claims, list):
        return ["claim_registry_claims_invalid"]
    manuscript = registry.get("manuscript")
    if not isinstance(manuscript, dict):
        reasons.append("claim_registry_manuscript_invalid")
    from experiments import synthetic_bench as bench

    by_id = {}
    for claim in claims:
        if not isinstance(claim, dict):
            reasons.append("claim_registry_entry_invalid")
            continue
        claim_id = claim.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            reasons.append("claim_id_invalid")
            continue
        if claim_id in by_id:
            reasons.append(f"claim_id_duplicate:{claim_id}")
        by_id[claim_id] = claim
        for field in CLAIM_REQUIRED_FIELDS:
            if field not in claim:
                reasons.append(f"claim_field_missing:{claim_id}:{field}")
        for field in ("manuscript_anchor", "text_anchor", "numerator",
                      "denominator", "baseline_driver", "generator_dataset",
                      "task_relationship", "historical_source_identity"):
            if not isinstance(claim.get(field), str) or not claim.get(field):
                reasons.append(f"claim_field_invalid:{claim_id}:{field}")
        if not isinstance(claim.get("dimensions_case_identity"), list) or \
                not claim.get("dimensions_case_identity"):
            reasons.append(
                f"claim_field_invalid:{claim_id}:dimensions_case_identity")
        evidence = claim.get("evidence_class")
        if not isinstance(evidence, str) or evidence not in EVIDENCE_CLASSES:
            reasons.append(f"claim_evidence_class_invalid:{claim_id}")
        mapping = claim.get("artifact_case_mapping")
        mapping_required = evidence == "current-artifact" or \
            mapping is not None
        mapping_valid = (isinstance(mapping, list) and bool(mapping) and
                         all(isinstance(case_id, str) and case_id
                             for case_id in mapping))
        if mapping_required and not mapping_valid:
            reasons.append(f"claim_artifact_mapping_invalid:{claim_id}")
        if mapping_valid:
            if len(mapping) != len(set(mapping)):
                reasons.append(f"claim_artifact_mapping_duplicate:{claim_id}")
            for case_id in dict.fromkeys(mapping):
                if case_id not in bench.CANONICAL_CASES_BY_ID:
                    reasons.append(
                        f"claim_artifact_mapping_unknown:{claim_id}:{case_id}")
            expected_mapping = EXPECTED_ARTIFACT_CASE_MAPPINGS.get(claim_id)
            if expected_mapping is not None and tuple(mapping) != \
                    expected_mapping:
                reasons.append(
                    f"claim_artifact_mapping_semantic_mismatch:{claim_id}")
        expected_direction = EXPECTED_RATIO_DIRECTIONS.get(claim_id)
        if claim.get("ratio_direction") != expected_direction:
            reasons.append(f"claim_ratio_direction_invalid:{claim_id}")
        scope = claim.get("machine_protocol_scope")
        if not isinstance(scope, dict) or not scope.get("machine") or \
                not scope.get("protocol"):
            reasons.append(f"claim_machine_scope_invalid:{claim_id}")
        if evidence == "historical-unconfirmed" and isinstance(scope, dict) \
                and scope.get("machine") == "metronforge-laptop-ref-01":
            reasons.append(
                f"claim_historical_scope_masquerades_as_current:{claim_id}")
        if evidence in ("different-task", "different-generator") and \
                claim.get("task_relationship") == "direct-reproduction":
            reasons.append(f"claim_evidence_not_direct:{claim_id}")
        if evidence == "historical-confirmed":
            reasons.append(
                f"claim_historical_confirmation_unsupported:{claim_id}")
        if evidence != "current-artifact" and \
                claim.get("publication_status") == "publication-ready":
            reasons.append(f"claim_unsupported_evidence_ready:{claim_id}")
        if claim.get("publication_status") not in (
                "publication-ready", "publication-blocker"):
            reasons.append(f"claim_publication_status_invalid:{claim_id}")
        for observation_name in ("historical_observation",
                                 "candidate_observation"):
            if observation_name in claim and not isinstance(
                    claim.get(observation_name), dict):
                reasons.append(
                    f"claim_observation_invalid:{claim_id}:"
                    f"{observation_name}")
        if manuscript_text is not None and isinstance(claim.get("text_anchor"),
                                                      str) and \
                claim["text_anchor"] not in manuscript_text:
            reasons.append(f"claim_text_anchor_missing:{claim_id}")
        if claim_id == "wide_extreme.32x12800":
            historical = claim.get("historical_observation")
            candidate = claim.get("candidate_observation")
            if not isinstance(historical, dict):
                historical = {}
            if not isinstance(candidate, dict):
                candidate = {}
            contradiction = (historical.get("dgelsy_over_router") !=
                             candidate.get("dgelsy_over_router"))
            if contradiction and (claim.get("publication_status") ==
                                  "publication-ready" or evidence ==
                                  "current-artifact"):
                reasons.append(
                    "claim_extreme_wide_contradiction_unresolved:"
                    "wide_extreme.32x12800")
        if claim_id == "grouped.lsmr":
            candidate = claim.get("candidate_observation")
            values = candidate.get("lsmr_over_router") \
                if isinstance(candidate, dict) else None
            if not (isinstance(values, list) and len(values) == 3 and
                    all(_finite_number(value) for value in values)):
                reasons.append(
                    "claim_grouped_observation_invalid:grouped.lsmr")

    for claim_id in sorted(REQUIRED_PERFORMANCE_CLAIM_IDS - set(by_id)):
        reasons.append(f"manuscript_claim_unmapped:{claim_id}")
    for claim_id in sorted(set(by_id) - REQUIRED_PERFORMANCE_CLAIM_IDS):
        reasons.append(f"claim_registry_unexpected:{claim_id}")

    if manuscript_text is not None:
        expected_hash = manuscript.get("sha256") \
            if isinstance(manuscript, dict) else None
        actual_hash = hashlib.sha256(manuscript_text.encode()).hexdigest()
        if expected_hash != actual_hash:
            reasons.append("manuscript_source_hash_mismatch")
    return list(dict.fromkeys(reasons))


def evaluate_performance_claims(registry, benchmark_protocol=None,
                                manuscript_text=None):
    """Keep protocol, claim coverage, and readiness as separate verdicts."""
    if manuscript_text is None:
        manuscript_text = (ROOT / "paper.tex").read_text()
    coverage_reasons = validate_performance_claim_registry(
        registry, manuscript_text=manuscript_text)
    blockers = []
    claims = registry.get("claims", []) if isinstance(registry, dict) else []
    if not isinstance(claims, list):
        claims = []
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(
                claim.get("claim_id"), str) or not claim["claim_id"]:
            continue
        if claim.get("publication_status") != "publication-ready" or \
                claim.get("evidence_class") != "current-artifact":
            blockers.append(f"manuscript_blocker:{claim['claim_id']}")
    if coverage_reasons:
        blockers.extend(coverage_reasons)
    return {
        "benchmark_protocol_eligibility": benchmark_protocol or {
            "eligible": False, "reasons": ["benchmark_protocol_not_audited"]},
        "manuscript_claim_coverage": {
            "complete": not coverage_reasons, "reasons": coverage_reasons},
        "manuscript_publication_readiness": {
            "ready": not blockers, "reasons": list(dict.fromkeys(blockers))},
    }


def parse_candidate_csv(path):
    """Normalize the public CSV representation to schema-v2 JSON values."""
    from experiments import synthetic_bench as bench

    integer_fields = {"schema_version", "m", "n", "rank", "rank_lo",
                      "rank_hi"}
    float_fields = {"berr", "router_s", "baseline_s", "router_mad_s",
                    "baseline_mad_s", "baseline_over_router",
                    "historical_ratio_min", "historical_ratio_max"}
    bool_fields = {"historical_claim_applicable", "numerical_valid"}
    json_fields = {"historical_claim_scope", "router_timings_s",
                   "baseline_timings_s", "baseline_diagnostics"}
    nullable_strings = {"historical_claim"}
    rows = []
    reasons = []
    try:
        with Path(path).open(newline="") as stream:
            reader = csv.DictReader(stream)
            if (not isinstance(reader.fieldnames, list) or
                    len(reader.fieldnames) != len(set(reader.fieldnames)) or
                    set(reader.fieldnames) != set(bench.ROW_REQUIRED_FIELDS)):
                return [], ["candidate_csv_schema_invalid"]
            for row_number, raw in enumerate(reader, 2):
                normalized = {}
                for field in bench.ROW_REQUIRED_FIELDS:
                    value = raw.get(field)
                    try:
                        if field in integer_fields:
                            normalized[field] = int(value)
                        elif field in float_fields:
                            parsed = None if value == "" else float(value)
                            normalized[field] = (
                                None if field == "berr" and
                                isinstance(parsed, float) and
                                math.isnan(parsed) else parsed)
                        elif field in bool_fields:
                            if value not in ("True", "False"):
                                raise ValueError("invalid boolean")
                            normalized[field] = value == "True"
                        elif field in json_fields:
                            normalized[field] = (None if value == ""
                                                 else json.loads(value))
                        elif field in nullable_strings and value == "":
                            normalized[field] = None
                        else:
                            normalized[field] = value
                    except (TypeError, ValueError, json.JSONDecodeError):
                        reasons.append(
                            f"candidate_csv_field_invalid:{row_number}:{field}")
                rows.append(normalized)
    except (OSError, UnicodeError, csv.Error):
        reasons.append("candidate_csv_invalid")
    return rows, list(dict.fromkeys(reasons))


def compare_candidate_rows(csv_rows, metadata_rows):
    """Compare normalized CSV and metadata rows without raising on damage."""
    reasons = []
    if not isinstance(csv_rows, list):
        return ["candidate_csv_rows_invalid"]
    if not isinstance(metadata_rows, list):
        return ["candidate_metadata_results_invalid"]

    def valid_rows(rows, label):
        normalized = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                reasons.append(f"candidate_{label}_row_invalid:{index}")
                continue
            case_id = row.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                reasons.append(
                    f"candidate_{label}_case_id_invalid:{index}")
                continue
            normalized.append((case_id, row))
        return normalized

    valid_csv = valid_rows(csv_rows, "csv")
    valid_metadata = valid_rows(metadata_rows, "metadata")
    csv_ids = [case_id for case_id, _ in valid_csv]
    metadata_ids = [case_id for case_id, _ in valid_metadata]
    csv_counts = Counter(csv_ids)
    metadata_counts = Counter(metadata_ids)
    if any(count > 1 for count in csv_counts.values()):
        reasons.append("candidate_csv_case_duplicate")
    if any(metadata_counts[case_id] > csv_counts[case_id]
           for case_id in metadata_counts):
        reasons.append("candidate_csv_row_missing")
    if any(csv_counts[case_id] > metadata_counts[case_id]
           for case_id in csv_counts):
        reasons.append("candidate_csv_row_extra")
    if csv_counts == metadata_counts and csv_ids != metadata_ids:
        reasons.append("candidate_csv_order_mismatch")

    csv_by_id = {case_id: row for case_id, row in valid_csv
                 if csv_counts[case_id] == 1}
    metadata_by_id = {case_id: row for case_id, row in valid_metadata
                      if metadata_counts[case_id] == 1}
    for case_id in metadata_ids:
        if case_id in csv_by_id and case_id in metadata_by_id and \
                csv_by_id[case_id] != metadata_by_id[case_id]:
            reasons.append(f"candidate_csv_metadata_divergence:{case_id}")
    return list(dict.fromkeys(reasons))


def audit_candidate_package(package_root, registry=None):
    """Read-only audit of the immutable PR #34 package."""
    from experiments import synthetic_bench as bench

    if registry is None:
        registry = load_performance_claim_registry()
    package_root = Path(package_root)
    integrity_reasons = []
    registry_dict = registry if isinstance(registry, dict) else {}
    artifact = registry_dict.get("candidate_artifact")
    if not isinstance(artifact, dict):
        integrity_reasons.append("artifact_registry_invalid")
        artifact = {}
    paths = {}
    records = {}
    for name in ("csv", "metadata", "checksum"):
        record = artifact.get(name)
        if not isinstance(record, dict):
            integrity_reasons.append(
                f"artifact_registry_record_invalid:{name}")
            record = {}
        records[name] = record
        relative_path = _safe_git_path(record.get("path"))
        if relative_path is None:
            integrity_reasons.append(f"artifact_registry_path_invalid:{name}")
            path = package_root / f".invalid-{name}"
        else:
            path = package_root / relative_path
        paths[name] = path
        expected_hash = record.get("sha256")
        if not _valid_hex(expected_hash, 64):
            integrity_reasons.append(f"artifact_registry_hash_invalid:{name}")
        if not path.is_file():
            integrity_reasons.append(f"artifact_missing:{name}")
        elif _sha256(path) != expected_hash:
            integrity_reasons.append(f"artifact_hash_mismatch:{name}")

    metadata = None
    csv_rows = []
    if paths["csv"].is_file():
        csv_rows, csv_reasons = parse_candidate_csv(paths["csv"])
        integrity_reasons.extend(csv_reasons)
    if paths["metadata"].is_file():
        try:
            metadata = json.loads(paths["metadata"].read_text())
        except (OSError, UnicodeError, json.JSONDecodeError):
            integrity_reasons.append("artifact_metadata_invalid")
    if isinstance(metadata, dict):
        integrity_reasons.extend(compare_candidate_rows(
            csv_rows, metadata.get("results")))
    if paths["checksum"].is_file():
        try:
            listed = {}
            for line in paths["checksum"].read_text().splitlines():
                digest, filename = line.split(maxsplit=1)
                listed[filename.lstrip("* ")] = digest
            for name in ("csv", "metadata"):
                expected_name = paths[name].name
                if listed.get(expected_name) != records[name].get("sha256"):
                    integrity_reasons.append(
                        f"artifact_checksum_entry_mismatch:{name}")
        except (OSError, UnicodeError, ValueError):
            integrity_reasons.append("artifact_checksum_invalid")

    protocol_reasons = []
    source_sha = artifact.get("source_sha")
    source_tree = artifact.get("source_tree")
    if not _valid_hex(source_sha, 40) or not _valid_hex(source_tree, 40):
        protocol_reasons.append("candidate_source_identity_invalid")
    else:
        actual_source_tree = _git_commit_tree(source_sha)
        if actual_source_tree is None:
            protocol_reasons.append("candidate_source_commit_missing")
        elif actual_source_tree != source_tree:
            protocol_reasons.append("candidate_source_commit_tree_mismatch")
    if isinstance(metadata, dict):
        def metadata_dict(name, reason):
            value = metadata.get(name)
            if not isinstance(value, dict):
                protocol_reasons.append(reason)
                return {}
            return value

        source = metadata_dict("source", "candidate_source_invalid")
        benchmark = metadata_dict("benchmark", "candidate_benchmark_invalid")
        build = metadata_dict(
            "build_provenance", "candidate_build_provenance_invalid")
        stored = metadata_dict(
            "publication_eligibility",
            "candidate_stored_protocol_invalid")
        rows = metadata.get("results")
        if source.get("git_sha") != artifact.get("source_sha"):
            protocol_reasons.append("candidate_source_sha_mismatch")
        if source.get("git_tree_sha") != artifact.get("source_tree"):
            protocol_reasons.append("candidate_source_tree_mismatch")
        if source.get("git_dirty") is not False:
            protocol_reasons.append("candidate_source_not_clean")
        for field, expected in (("seed", bench.CANONICAL_SEED),
                                ("driver", bench.CANONICAL_DRIVER),
                                ("scale", 1.0), ("repeats", 11),
                                ("large_cases", True)):
            if benchmark.get(field) != expected:
                protocol_reasons.append(
                    f"candidate_benchmark_configuration_mismatch:{field}")
        if not build.get("verified") or build.get("reasons"):
            protocol_reasons.append("candidate_build_provenance_unverified")
        manifest = build.get("manifest")
        if not isinstance(manifest, dict):
            protocol_reasons.append("candidate_build_manifest_invalid")
            manifest = {}
        manifest_source = manifest.get("source")
        if not isinstance(manifest_source, dict):
            protocol_reasons.append("candidate_build_source_invalid")
            manifest_source = {}
        if (manifest_source.get("git_sha"),
                manifest_source.get("git_tree_sha"),
                manifest_source.get("git_dirty")) != (
                    artifact.get("source_sha"), artifact.get("source_tree"),
                    False):
            protocol_reasons.append("candidate_build_source_mismatch")
        manifest_router_record = manifest.get("router")
        if not isinstance(manifest_router_record, dict):
            manifest_router_record = {}
        manifest_router = manifest_router_record.get("library")
        if not isinstance(manifest_router, dict):
            protocol_reasons.append("candidate_router_record_invalid")
            manifest_router = {}
        if not manifest_router.get("sha256") or \
                manifest_router.get("sha256") != build.get("router_sha256"):
            protocol_reasons.append("candidate_router_identity_mismatch")
        thread_control = metadata_dict(
            "thread_control", "candidate_thread_control_invalid")
        for name in bench.REQUIRED_THREAD_CONTROLS:
            if thread_control.get(name) != "1":
                protocol_reasons.append(
                    f"candidate_thread_control_not_one:{name}")
        linear_algebra = metadata_dict(
            "linear_algebra", "candidate_linear_algebra_invalid")
        raw_blas_pools = linear_algebra.get("threadpools")
        if not isinstance(raw_blas_pools, list):
            protocol_reasons.append("candidate_blas_pools_invalid")
            raw_blas_pools = []
        blas_pools = []
        for index, pool in enumerate(raw_blas_pools):
            if not isinstance(pool, dict):
                protocol_reasons.append(
                    f"candidate_blas_pool_invalid:{index}")
            elif pool.get("user_api") == "blas":
                blas_pools.append(pool)
                if not _valid_hex(pool.get("sha256"), 64) or \
                        type(pool.get("num_threads")) is not int or \
                        pool["num_threads"] != 1:
                    protocol_reasons.append(
                        f"candidate_blas_pool_invalid:{index}")
        if not blas_pools:
            protocol_reasons.append("candidate_blas_provider_missing")
        elif any(type(pool.get("num_threads")) is not int or
                 pool.get("num_threads") != 1 for pool in blas_pools):
            protocol_reasons.append("candidate_blas_pool_not_single_thread")
        openblas = manifest.get("openblas")
        if not isinstance(openblas, dict):
            openblas = {}
        linked_blas = openblas.get("sha256")
        runtime_blas = {pool.get("sha256") for pool in blas_pools
                        if _valid_hex(pool.get("sha256"), 64)}
        if not _valid_hex(linked_blas, 64):
            protocol_reasons.append("candidate_linked_blas_hash_invalid")
        if not _valid_hex(linked_blas, 64) or \
                linked_blas not in runtime_blas:
            protocol_reasons.append("candidate_runtime_blas_identity_mismatch")
        machine = metadata_dict("machine", "candidate_machine_invalid")
        software = metadata_dict("software", "candidate_software_invalid")
        if any(machine.get(key) in (None, "") for key in
               ("cpu_model", "physical_cores", "logical_cores", "ram_bytes",
                "os", "kernel", "reference_name")):
            protocol_reasons.append("candidate_machine_identity_incomplete")
        if any(software.get(key) in (None, "") for key in
               ("python", "numpy", "scipy")):
            protocol_reasons.append("candidate_software_identity_incomplete")
        if stored != {"eligible": True, "reasons": []}:
            protocol_reasons.append("candidate_stored_protocol_ineligible")
        if not isinstance(rows, list) or len(rows) != len(
                bench.CANONICAL_REFERENCE_SIGNATURE):
            protocol_reasons.append("candidate_case_set_incomplete")
        if isinstance(rows, list):
            valid_rows = []
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                if not isinstance(row.get("case_id"), str) or not \
                        row.get("case_id"):
                    continue
                valid_rows.append(row)
            actual = tuple((row.get("case_id"), row.get("m"), row.get("n"),
                            row.get("baseline_kind")) for row in valid_rows)
            if actual != bench.CANONICAL_REFERENCE_SIGNATURE:
                protocol_reasons.append("candidate_case_signature_mismatch")
            for index, row in enumerate(valid_rows):
                try:
                    row_reasons = bench.validate_schema_v2_row(
                        row, benchmark.get("repeats", 0))
                except Exception:
                    row_reasons = [f"candidate_row_validation_error:{index}"]
                for reason in row_reasons:
                    if reason not in protocol_reasons:
                        protocol_reasons.append(reason)

            by_id = {row["case_id"]: row for row in valid_rows}
            extreme = by_id.get("wide_extreme.32x12800", {})
            raw_claims = registry_dict.get("claims")
            claims = raw_claims if isinstance(raw_claims, list) else []
            claims_by_id = {
                claim["claim_id"]: claim for claim in claims
                if isinstance(claim, dict) and
                isinstance(claim.get("claim_id"), str) and
                claim["claim_id"]}
            expected_extreme = claims_by_id.get("wide_extreme.32x12800")
            if expected_extreme is not None:
                observation = expected_extreme.get("candidate_observation")
                observed = observation.get("dgelsy_over_router") \
                    if isinstance(observation, dict) else None
                actual = extreme.get("baseline_over_router")
                if not (_finite_number(observed) and _finite_number(actual) and
                        math.isclose(actual, observed, rel_tol=1e-6)):
                    protocol_reasons.append(
                        "candidate_extreme_wide_value_mismatch")
            grouped = claims_by_id.get("grouped.lsmr")
            if grouped is not None:
                observation = grouped.get("candidate_observation")
                expected_grouped = observation.get("lsmr_over_router") \
                    if isinstance(observation, dict) else None
                mapping = grouped.get("artifact_case_mapping")
                actual_grouped = []
                if isinstance(mapping, list):
                    for case_id in mapping:
                        row = by_id.get(case_id) \
                            if isinstance(case_id, str) else None
                        ratio = row.get("baseline_over_router") \
                            if isinstance(row, dict) else None
                        if not _finite_number(ratio):
                            protocol_reasons.append(
                                "candidate_grouped_lsmr_ratio_invalid:"
                                f"{case_id}")
                        else:
                            actual_grouped.append(ratio)
                expected_valid = (
                    isinstance(expected_grouped, list) and
                    all(_finite_number(value) for value in expected_grouped))
                if not expected_valid or \
                        len(expected_grouped) != len(actual_grouped) or any(
                            not math.isclose(a, b, rel_tol=1e-6)
                            for a, b in zip(actual_grouped,
                                            expected_grouped)):
                    protocol_reasons.append(
                        "candidate_grouped_lsmr_value_mismatch")
    elif "artifact_metadata_invalid" not in integrity_reasons:
        protocol_reasons.append("candidate_metadata_missing")

    verdicts = evaluate_performance_claims(
        registry,
        benchmark_protocol={"eligible": not protocol_reasons,
                            "reasons": protocol_reasons})
    return {
        "artifact_integrity": {
            "valid": not integrity_reasons, "reasons": integrity_reasons},
        **verdicts,
    }


# --------------------------------------------------------------------------
# Claims taken verbatim from paper.tex.  The "where" field is the manuscript
# location, so a failure tells you which sentence to fix.
# --------------------------------------------------------------------------

EXACT_CLAIMS = [
    # (battery, json path, expected value, where in the paper)
    ("pbt_equivalence_orbits", ["checks"], 8335,
     "Abstract; sec:results 'executes 8,335 checks'"),
    ("pbt_equivalence_orbits",
     ["failure_counts_by_severity", "known-representation"], 154,
     "Abstract; sec:results '154 explicitly labelled ... affine-translation cases'"),
    ("pbt_certificate_equivariance", ["checks"], 2271,
     "Abstract; sec:results 'A second focused battery contains 2,271 ... checks'"),
]

# Floating-point measurements.  These are NOT deterministic across platforms:
# they depend on the LAPACK/BLAS build and the compiler.  Observed spread
# between two environments (local reference vs. GitHub runner):
#
#     inconsistent_eta_max     3.871e-15  vs  3.804e-15   (-1.7%)
#     inconsistent_eta_median  9.418e-17  vs  1.004e-16   (+6.6%)
#     shadow_ratio_max         2.000      vs  1.235
#
# Asserting the printed digits would therefore test the platform, not the
# code.  What the manuscript actually relies on is the SCALE -- accepted
# radii stay at machine precision -- so that is what is asserted here, with
# the observed value reported for the record.  The reference values are kept
# so a drift of orders of magnitude is still visible in the output.
APPROX_CLAIMS = []

BOUND_CLAIMS = [
    # (battery, json path, upper bound, reference value, where)
    ("pbt_certificate_equivariance", ["stats", "inconsistent_eta_max"],
     1e-14, 3.871e-15,
     "sec:results 'accepted inconsistency radii have maximum ...'"),
    ("pbt_certificate_equivariance", ["stats", "inconsistent_eta_median"],
     1e-15, 9.418e-17,
     "sec:results '... and median ...'"),
]

# Values the paper states as a range.  The LOWER bound here is the soundness
# statement -- "no sampled strict radius is below the shadow value" -- and
# must hold exactly.  The upper bound is descriptive of the sampled corpus.
RANGE_CLAIMS = [
    ("pbt_certificate_equivariance", ["stats", "shadow_ratio_min"], 1.0, 2.0,
     "sec:results 'no sampled strict radius is below the shadow value'"),
    ("pbt_certificate_equivariance", ["stats", "shadow_ratio_max"], 1.0, 2.0,
     "sec:results 'the strict/checker radius ratio ranges from 1 to 2'"),
]

# A hard failure in either battery is a failure regardless of counts.
NO_HARD_FAILURE = [
    ("pbt_certificate_equivariance", ["failure_counts"],
     "sec:results 'zero failure'"),
]


def dig(obj, path):
    """Walk a JSON path, returning None if any key is absent."""
    cur = obj
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def run_battery(name: str) -> dict:
    """Run one property battery and return its parsed JSON output."""
    script = TESTS / f"{name}.py"
    if not script.is_file():
        raise SystemExit(f"missing battery: {script}")
    proc = subprocess.run([sys.executable, str(script)],
                          capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"{name} exited with {proc.returncode}")
    text = proc.stdout.strip()
    start = text.find("{")
    if start < 0:
        raise SystemExit(f"{name}: no JSON found in output")
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{name}: cannot parse JSON: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true",
                    help="print the expected values without running anything")
    ap.add_argument("--check-performance-inventory", action="store_true",
                    help="validate the explicit performance-claim inventory")
    ap.add_argument("--audit-performance-artifacts", metavar="ROOT",
                    help="read-only audit of the immutable candidate package")
    ap.add_argument("--require-publication-ready", action="store_true",
                    help="fail when registered manuscript blockers remain")
    args = ap.parse_args()

    if args.check_performance_inventory or args.audit_performance_artifacts:
        registry = load_performance_claim_registry()
        if args.audit_performance_artifacts:
            report = audit_candidate_package(
                args.audit_performance_artifacts, registry)
        else:
            report = {
                "artifact_integrity": {
                    "valid": None, "reasons": ["artifact_not_audited"]},
                **evaluate_performance_claims(registry),
            }
        print(json.dumps(report, indent=2, sort_keys=True))
        ordinary_ok = (
            report["manuscript_claim_coverage"]["complete"] and
            (not args.audit_performance_artifacts or (
                report["artifact_integrity"]["valid"] and
                report["benchmark_protocol_eligibility"]["eligible"])))
        if args.require_publication_ready:
            ordinary_ok = ordinary_ok and \
                report["manuscript_publication_readiness"]["ready"]
        return 0 if ordinary_ok else 1

    if args.list:
        print("Exact claims:")
        for b, p, v, w in EXACT_CLAIMS:
            print(f"  {b}:{'.'.join(p)} == {v}   [{w}]")
        print("Bound claims (machine scale; exact digits are platform-dependent):")
        for b, p, bd, rf, w in BOUND_CLAIMS:
            print(f"  {b}:{'.'.join(p)} <= {bd:g} (reference {rf:g})   [{w}]")
        print("Range claims:")
        for b, p, lo, hi, w in RANGE_CLAIMS:
            print(f"  {b}:{'.'.join(p)} in [{lo}, {hi}]   [{w}]")
        return 0

    needed = sorted({c[0] for c in
                     EXACT_CLAIMS + APPROX_CLAIMS + BOUND_CLAIMS
                     + RANGE_CLAIMS + NO_HARD_FAILURE})
    results = {}
    for name in needed:
        print(f"running {name} ...", flush=True)
        results[name] = run_battery(name)

    failures = []
    checked = 0

    print()
    print("=" * 78)
    print("Manuscript claim reproduction")
    print("=" * 78)

    for battery, path, expected, where in EXACT_CLAIMS:
        got = dig(results[battery], path)
        checked += 1
        ok = got == expected
        print(f"  [{'ok ' if ok else 'FAIL'}] {battery}:{'.'.join(path)} "
              f"= {got}  (paper: {expected})")
        if not ok:
            failures.append(f"{battery}:{'.'.join(path)} is {got}, "
                            f"paper states {expected}  -- {where}")

    for battery, path, expected, tol, where in APPROX_CLAIMS:
        got = dig(results[battery], path)
        checked += 1
        ok = isinstance(got, (int, float)) and math.isfinite(got) and \
            abs(got - expected) <= tol * abs(expected)
        shown = f"{got:.6e}" if isinstance(got, (int, float)) else str(got)
        print(f"  [{'ok ' if ok else 'FAIL'}] {battery}:{'.'.join(path)} "
              f"= {shown}  (paper: {expected:.3e}, rel tol {tol})")
        if not ok:
            failures.append(f"{battery}:{'.'.join(path)} is {shown}, "
                            f"paper states {expected:.3e}  -- {where}")

    for battery, path, bound, reference, where in BOUND_CLAIMS:
        got = dig(results[battery], path)
        checked += 1
        ok = isinstance(got, (int, float)) and math.isfinite(got) and \
            0.0 <= got <= bound
        shown = f"{got:.6e}" if isinstance(got, (int, float)) else str(got)
        drift = (f", {got/reference:.2f}x reference"
                 if isinstance(got, (int, float)) and reference else "")
        print(f"  [{'ok ' if ok else 'FAIL'}] {battery}:{'.'.join(path)} "
              f"= {shown}  (must be <= {bound:.0e}{drift})")
        if not ok:
            failures.append(f"{battery}:{'.'.join(path)} is {shown}, "
                            f"which exceeds the machine-scale bound "
                            f"{bound:.0e}  -- {where}")

    for battery, path, lo, hi, where in RANGE_CLAIMS:
        got = dig(results[battery], path)
        checked += 1
        # Asymmetric on purpose, matching the comment on RANGE_CLAIMS: the
        # lower bound is the soundness statement and admits no slack, while
        # the upper bound is descriptive of the sampled corpus and a value one
        # ulp over it is a property of the platform.  The check used to apply
        # 1e-12 to both sides, which would have passed a shadow ratio of
        # 0.9999999999995 -- a strict radius below the shadow value, which is
        # the one thing this claim exists to exclude.
        ok = isinstance(got, (int, float)) and lo <= got <= hi + 1e-12
        shown = f"{got:.6f}" if isinstance(got, (int, float)) else str(got)
        print(f"  [{'ok ' if ok else 'FAIL'}] {battery}:{'.'.join(path)} "
              f"= {shown}  (paper: within [{lo}, {hi}])")
        if not ok:
            failures.append(f"{battery}:{'.'.join(path)} is {shown}, "
                            f"paper states [{lo}, {hi}]  -- {where}")

    for battery, path, where in NO_HARD_FAILURE:
        got = dig(results[battery], path)
        checked += 1
        ok = got == {} or got == {} if isinstance(got, dict) else False
        ok = isinstance(got, dict) and len(got) == 0
        print(f"  [{'ok ' if ok else 'FAIL'}] {battery}:{'.'.join(path)} "
              f"is empty  (paper: zero failure)")
        if not ok:
            failures.append(f"{battery}:{'.'.join(path)} is {got}, "
                            f"paper states zero failure  -- {where}")

    print()
    if failures:
        print(f"{len(failures)} of {checked} claims NOT reproduced:")
        for f in failures:
            print(f"  - {f}")
        print()
        print("A mismatch here means a sentence in paper.tex is now wrong.")
        print("Either the code changed behaviour or the manuscript needs an update;")
        print("do not silently adjust the expected values in this file.")
        return 1

    print(f"all {checked} manuscript claims reproduced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
