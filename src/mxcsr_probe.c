/*
 * mxcsr_probe.c -- Build-time probe: the fast library must not alter the process FP mode.
 *
 * Copyright 2026 Viktor Mikhalkin
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
/* mxcsr_probe.c -- runtime check that the fast library does not change the
 * process-wide floating-point mode.
 *
 * Rationale.  build.sh compiles the fast router with -ffast-math and the
 * proof kernels with -frounding-math -fno-fast-math.  Separate compilation
 * is necessary but NOT sufficient: on some toolchains a -ffast-math link
 * pulls in crtfastmath.o, whose constructor sets the FTZ (flush-to-zero)
 * and DAZ (denormals-are-zero) bits of MXCSR for the WHOLE PROCESS at load
 * time.  Those bits are runtime state, not a compile-time property, so they
 * would then also apply to the strict checker running in the same process.
 *
 * That would silently invalidate exactly the tests the certificate battery
 * relies on: it exercises "global verifier scales from deep subnormal
 * values through 2^1020".  Under FTZ/DAZ those subnormal inputs become
 * zero and the corresponding checks pass vacuously.
 *
 * This probe therefore loads the fast library and the certified API in the
 * same order the Python harnesses do, and fails the build if either the
 * control bits change or a subnormal stops surviving a multiplication.
 *
 * Exit status: 0 = mode preserved, 1 = mode changed (build should fail).
 */

#include <stdio.h>
#include <dlfcn.h>

#if defined(__x86_64__) || defined(__i386__)
#include <xmmintrin.h>
#define BS_HAVE_MXCSR 1
static unsigned bs_csr(void) { return _mm_getcsr(); }
#define BS_FTZ(m) (((m) >> 15) & 1u)
#define BS_DAZ(m) (((m) >> 6) & 1u)
#else
#define BS_HAVE_MXCSR 0
#endif

/* volatile so the compiler cannot fold the subnormal arithmetic away */
static volatile double bs_tiny = 5e-324; /* smallest positive binary64 subnormal */

static int subnormal_survives(void) {
    volatile double r = bs_tiny * 1.0;
    return r != 0.0;
}

int main(int argc, char **argv) {
    const char *fast = (argc > 1) ? argv[1] : "./libaffine_bundle_solver.so";
    const char *cert = (argc > 2) ? argv[2] : "./libcertified_solver.so";
    int failed = 0;

#if BS_HAVE_MXCSR
    unsigned before = bs_csr();
    unsigned ftz0 = BS_FTZ(before), daz0 = BS_DAZ(before);
#endif
    int sub0 = subnormal_survives();

    void *h1 = dlopen(fast, RTLD_NOW);
    if (!h1) {
        fprintf(stderr, "mxcsr probe: cannot load %s: %s\n", fast, dlerror());
        return 2;
    }
    int sub1 = subnormal_survives();

    void *h2 = dlopen(cert, RTLD_NOW);
    /* the certified library is optional for this probe */
    int sub2 = subnormal_survives();

#if BS_HAVE_MXCSR
    unsigned after = bs_csr();
    unsigned ftz1 = BS_FTZ(after), daz1 = BS_DAZ(after);
    if (ftz1 != ftz0 || daz1 != daz0) {
        fprintf(stderr,
                "mxcsr probe: FAIL -- loading the fast library changed the "
                "FP mode (FTZ %u->%u, DAZ %u->%u).  Subnormal-range "
                "certificate tests would be vacuous.\n",
                ftz0, ftz1, daz0, daz1);
        failed = 1;
    }
#endif

    if (!(sub0 && sub1 && sub2)) {
        fprintf(stderr,
                "mxcsr probe: FAIL -- a subnormal was flushed to zero "
                "(before=%d, after fast=%d, after certified=%d).\n",
                sub0, sub1, sub2);
        failed = 1;
    }

    if (!failed) {
#if BS_HAVE_MXCSR
        printf("mxcsr probe: PASS (FTZ=%u DAZ=%u unchanged, subnormals "
               "preserved)\n", ftz1, daz1);
#else
        printf("mxcsr probe: PASS (subnormals preserved; MXCSR check "
               "skipped on this architecture)\n");
#endif
    }

    if (h2) dlclose(h2);
    dlclose(h1);
    return failed;
}
