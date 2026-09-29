"""The runtime gate must reject load errors and constructors changing FP state."""
import pathlib
import subprocess
import sys
import tempfile

probe, cc = sys.argv[1:]
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    source = root / "constructor.c"
    suffix = ".dylib" if sys.platform == "darwin" else ".so"
    libraries = {}
    for mode, body in {
        "clean": "",
        "rounding": "fesetround(FE_UPWARD);",
        "flush": """
#if defined(__aarch64__)
unsigned long x; __asm__ volatile("mrs %0, fpcr" : "=r"(x));
x |= 1ul << 24; __asm__ volatile("msr fpcr, %0" :: "r"(x));
#elif defined(__x86_64__) || defined(__i386__)
_mm_setcsr(_mm_getcsr() | (1u << 15) | (1u << 6));
#else
#error Unsupported architecture
#endif
""",
    }.items():
        source.write_text("""#include <fenv.h>
#if defined(__x86_64__) || defined(__i386__)
#include <xmmintrin.h>
#endif
__attribute__((constructor)) static void init(void) {
""" + body + "\n}\n")
        path = root / (mode + suffix)
        subprocess.run([cc, "-dynamiclib" if sys.platform == "darwin" else "-shared",
                        "-fPIC", str(source), "-o", str(path), "-lm"], check=True)
        libraries[mode] = path
    for first, second, success in [
        ("clean", "clean", True), ("clean", "missing", False),
        ("rounding", "clean", False), ("clean", "rounding", False),
        ("flush", "clean", False), ("clean", "flush", False),
    ]:
        paths = [str(libraries.get(name, root / "missing")) for name in (first, second)]
        result = subprocess.run([probe, *paths], capture_output=True, text=True)
        assert (result.returncode == 0) == success, (first, second, result.stdout, result.stderr)
        print(f"FP environment negative control {first}/{second}: PASS")
