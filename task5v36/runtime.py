"""Runtime policies, direct thread control, and fail-closed telemetry."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from threadpoolctl import ThreadpoolController


THREAD_VARIABLES = (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS", "OMP_DYNAMIC", "MKL_DYNAMIC",
)
NUMERIC_TOKENS = ("blas", "lapack", "mkl", "gomp", "iomp")
TELEMETRY_KEYS = {
    "proc_maps", "loaded_numeric_libraries", "threadpools",
    "process_affinity", "process_status_threads", "cpu_topology", "governors",
    "turbo", "frequencies_khz", "temperatures_millic", "throttle",
    "environment", "runtime_settings",
}


@dataclass(frozen=True)
class RolePolicy:
    name: str
    active_threads: int
    system_openblas_threads: int
    scipy_blas_threads: int
    mkl_threads: int
    gomp_threads: int
    iomp_threads: int
    forbidden_tokens: tuple[str, ...] = ()


@dataclass(frozen=True)
class Configuration:
    name: str
    active_threads: int
    inactive_threads: int
    cpu_set: str
    selectable: bool
    mixed_runtime: bool
    roles: dict[str, RolePolicy]


def _solver(active, *, forbid=True):
    return RolePolicy(
        "solver", active, active, 1, 1, 1, 1,
        ("scipy_openblas", "libmkl", "libiomp") if forbid else (),
    )


def _legacy(active):
    return RolePolicy("legacy", active, 1, active, 1, 1, 1)


def _mixed(active):
    return RolePolicy("mixed", active, active, active, active, active, active)


CONFIGURATIONS = {
    "C1": Configuration("C1", 4, 1, "1,3,6,8", True, False,
                         {"solver": _solver(4), "legacy": _legacy(4)}),
    "C2": Configuration("C2", 1, 1, "1", True, False,
                         {"solver": _solver(1), "legacy": _legacy(1)}),
    "C3": Configuration(
        "C3", 4, 4, "1,3,6,8", False, True,
        {"solver": _mixed(4), "legacy": _mixed(4)},
    ),
}


_LIMITERS = []


def _desired_threads(filepath, policy):
    lower = filepath.lower()
    if "scipy_openblas" in lower:
        return policy.scipy_blas_threads
    if "openblas" in lower:
        return policy.system_openblas_threads
    if "mkl" in lower:
        return policy.mkl_threads
    if "libiomp" in lower:
        return policy.iomp_threads
    if "libgomp" in lower:
        return policy.gomp_threads
    return 1


def apply_runtime_policy(policy):
    """Set each already-loaded runtime directly and return effective settings."""
    controller = ThreadpoolController()
    requested = {}
    for info in controller.info():
        filepath = info.get("filepath") or ""
        if not filepath:
            continue
        desired = _desired_threads(filepath, policy)
        _LIMITERS.append(controller.select(filepath=filepath).limit(limits=desired))
        requested[filepath] = desired
    effective = {}
    for info in ThreadpoolController().info():
        filepath = info.get("filepath") or ""
        if filepath:
            effective[filepath] = {
                "requested": requested.get(filepath),
                "effective": info.get("num_threads"),
                "internal_api": info.get("internal_api"),
                "user_api": info.get("user_api"),
            }
    return effective


def _read(path, cast=str):
    try:
        return cast(Path(path).read_text().strip())
    except (OSError, ValueError):
        return None


def _proc_maps():
    return Path("/proc/self/maps").read_text().splitlines()


def _numeric_libraries(maps):
    paths = set()
    for line in maps:
        path = line.split()[-1] if "/" in line else ""
        if path and any(token in path.lower() for token in NUMERIC_TOKENS):
            paths.add(path)
    return sorted(paths)


def _status_threads():
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("Threads:"):
            return int(line.split()[1])
    raise RuntimeError("/proc/self/status has no Threads field")


def _topology(cpus):
    result = []
    for cpu in cpus:
        base = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        result.append({"cpu": cpu, "core": _read(base / "core_id", int),
                       "package": _read(base / "physical_package_id", int)})
    return result


def _turbo():
    no_turbo = _read("/sys/devices/system/cpu/intel_pstate/no_turbo", int)
    if no_turbo is not None:
        return {"enabled": no_turbo == 0, "source": "intel_pstate/no_turbo"}
    boost = _read("/sys/devices/system/cpu/cpufreq/boost", int)
    return {"enabled": None if boost is None else bool(boost),
            "source": "cpufreq/boost" if boost is not None else "unavailable"}


def _thermal_throttle():
    signals = {}
    for path in Path("/sys/devices/system/cpu").glob(
            "cpu*/thermal_throttle/*_throttle_count"):
        value = _read(path, int)
        if value is not None:
            signals[str(path)] = value
    return {"observed": False, "signals": signals}


def capture_telemetry(runtime_settings=None):
    maps = _proc_maps()
    affinity = sorted(os.sched_getaffinity(0))
    pools = []
    for info in ThreadpoolController().info():
        pools.append({key: info.get(key) for key in (
            "filepath", "prefix", "user_api", "internal_api", "num_threads",
            "version", "threading_layer", "architecture")})
    governors = {str(cpu): _read(
        f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor")
        for cpu in affinity}
    frequencies = {str(cpu): _read(
        f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq", int)
        for cpu in affinity}
    temperatures = [value for value in (
        _read(path, int) for path in Path("/sys/class/thermal").glob(
            "thermal_zone*/temp")) if value is not None]
    return {
        "proc_maps": maps,
        "loaded_numeric_libraries": _numeric_libraries(maps),
        "threadpools": pools,
        "process_affinity": affinity,
        "process_status_threads": _status_threads(),
        "cpu_topology": _topology(affinity),
        "governors": governors,
        "turbo": _turbo(),
        "frequencies_khz": frequencies,
        "temperatures_millic": temperatures,
        "throttle": _thermal_throttle(),
        "environment": {name: os.environ.get(name) for name in THREAD_VARIABLES},
        "runtime_settings": runtime_settings or {},
    }


def validate_telemetry(value):
    missing = sorted(TELEMETRY_KEYS - set(value))
    if missing:
        raise ValueError(f"missing telemetry fields: {','.join(missing)}")
    if not value["proc_maps"] or not value["process_affinity"]:
        raise ValueError("empty proc_maps or process_affinity")
    return value


def fingerprint_identity(telemetry):
    validate_telemetry(telemetry)
    return {
        "libraries": sorted(telemetry["loaded_numeric_libraries"]),
        "threadpools": sorted((item.get("filepath") or "",
                               item.get("internal_api"), item.get("num_threads"))
                              for item in telemetry["threadpools"]),
        "affinity": telemetry["process_affinity"],
        "runtime_settings": telemetry["runtime_settings"],
    }


def fingerprint_eligible(telemetry, policy):
    validate_telemetry(telemetry)
    reasons = []
    libraries = [path.lower() for path in telemetry["loaded_numeric_libraries"]]
    for token in policy.forbidden_tokens:
        if any(token in path for path in libraries):
            reasons.append(f"forbidden_runtime:{token}")
    for pool in telemetry["threadpools"]:
        filepath = pool.get("filepath") or ""
        expected = _desired_threads(filepath, policy)
        if pool.get("num_threads") != expected:
            reasons.append(
                f"thread_mismatch:{Path(filepath).name}:{pool.get('num_threads')}!={expected}")
    if not telemetry["threadpools"]:
        reasons.append("no_runtime_threadpool_evidence")
    return {"passed": not reasons, "reasons": reasons,
            "identity": fingerprint_identity(telemetry)}


def environment_for(policy):
    values = {
        "OPENBLAS_NUM_THREADS": str(policy.system_openblas_threads),
        "OMP_NUM_THREADS": str(policy.gomp_threads),
        "MKL_NUM_THREADS": str(policy.mkl_threads),
        "BLIS_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "OMP_DYNAMIC": "FALSE",
        "MKL_DYNAMIC": "FALSE",
    }
    return values
