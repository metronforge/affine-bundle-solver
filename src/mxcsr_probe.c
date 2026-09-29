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
 * proof kernels with -frounding-math -fno-fast-math -ffp-contract=off.
 * Separate compilation is necessary but NOT sufficient: on some toolchains
 * a -ffast-math link pulls in crtfastmath.o, whose constructor sets the FTZ
 * (flush-to-zero) and DAZ (denormals-are-zero) bits of MXCSR for the WHOLE
 * PROCESS at load time.  Those bits are runtime state, not a compile-time
 * property, so they would then also apply to the strict checker running in
 * the same process.
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
#include <fenv.h>
#include <float.h>
#include <stdint.h>
#include <inttypes.h>
#pragma STDC FENV_ACCESS ON

#if defined(__x86_64__) || defined(__i386__)
#include <xmmintrin.h>
#define BS_REGISTER "MXCSR"
/* Status flags [5:0] may legitimately change; all control bits must stay. */
static uint64_t bs_control(void) { return _mm_getcsr() & ~UINT64_C(63); }
#elif defined(__aarch64__)
#define BS_REGISTER "FPCR"
/* FPCR is user-readable. FPSR holds exception status separately. Comparing
 * all FPCR bits includes FZ, rounding, DN, FZ16 and implemented AH/FIZ bits.
 * Unlike x86 DAZ, baseline Arm FZ controls both input and output flushing. */
static uint64_t bs_control(void) {
    uint64_t value;
    __asm__ volatile("mrs %0, fpcr" : "=r"(value));
    return value;
}
#else
#error Cannot inspect floating-point control state on this architecture
#endif

/* volatile so the compiler cannot fold the subnormal arithmetic away */
static volatile double bs_tiny = 5e-324; /* smallest positive binary64 subnormal */
static volatile double bs_two = 2.0;
static volatile double bs_normal = DBL_MIN;
static volatile double bs_half = 0.5;

static int subnormal_survives(void) {
    volatile double input = bs_tiny * bs_two;
    volatile double output = bs_normal * bs_half;
    return input == 0x0.0000000000002p-1022 && output == 0x0.8p-1022;
}

static int rounding_survives(void) {
    int old = fegetround();
    volatile double one = 1.0, half_ulp = 0x1p-53;
    volatile double down, up;
    if (old < 0 || fesetround(FE_DOWNWARD)) return 0;
    down = one + half_ulp;
    if (fesetround(FE_UPWARD)) return 0;
    up = one + half_ulp;
    if (fesetround(old)) return 0;
    return down == 1.0 && up == 0x1.0000000000001p0;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s FAST_LIBRARY CERTIFIED_LIBRARY\n", argv[0]);
        return 2;
    }
    uint64_t before = bs_control();
    for (int stage = 0; stage < 3; ++stage) {
        if (stage && !dlopen(argv[stage], RTLD_NOW)) {
            fprintf(stderr, "FP environment probe: cannot load %s: %s\n",
                    argv[stage], dlerror());
            return 2;
        }
        uint64_t after = bs_control();
        if (before != after || !subnormal_survives() || !rounding_survives()
            || bs_control() != before) {
            fprintf(stderr, "FP environment probe: FAIL stage=%d " BS_REGISTER
                    " control=0x%" PRIx64 " -> 0x%" PRIx64
                    " (control state, subnormals or rounding violated)\n",
                    stage, before, after);
            return 1;
        }
    }
    printf("FP environment probe: PASS (" BS_REGISTER " control=0x%" PRIx64
           " unchanged; input/output subnormals and directed rounding preserved)\n", before);
    /* Keep both DSOs loaded until process exit. This probe checks load-time
       FP mode, not unload behavior; dlclose can leave the dynamic loader's
       own TLS bookkeeping unreachable to LSan on hosted CI runners. The
       native solver lifecycle tests check library allocations separately. */
    return 0;
}
