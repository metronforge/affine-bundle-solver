import os
import subprocess
import sys
from pathlib import Path


THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
               "BLIS_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def build_qrcp_input_tracer(out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).with_name("qrcp_input_trace.c")
    output = out_dir / "libtask5v33_qrcp_input_trace.so"
    subprocess.run(["cc", "-std=c11", "-O2", "-fPIC", "-shared", str(source),
                    "-ldl", "-o", str(output)], check=True)
    return output


def parse_qrcp_input_trace(stderr):
    line = next(line for line in stderr.splitlines()
                if line.startswith("QRCP_INPUT_TRACE "))
    result = {}
    for field in line.split()[1:]:
        key, value = field.split("=", 1)
        if key == "hashes":
            result[key] = [] if not value else value.split(",")
        elif key == "storage":
            result[key] = value
        else:
            result[key] = int(value)
    return result


def run_v31_027(solver_lib, tracer):
    environment = os.environ.copy()
    for name in THREAD_VARS:
        environment[name] = "4"
    environment.update({"TASK5_SOLVER_LIB": str(solver_lib),
                        "LD_PRELOAD": str(tracer)})
    command = [sys.executable, "-m", "task5v32.native_trial", "--slot", "V31-027"]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=environment, check=True)
    return {"command": command, "stdout": completed.stdout,
            "stderr": completed.stderr,
            "trace": parse_qrcp_input_trace(completed.stderr)}
