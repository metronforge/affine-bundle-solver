/*
 * rounding_probe.c -- Build-time probe: directed rounding must be distinguishable.
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
#pragma STDC FENV_ACCESS ON
#include <fenv.h>
#include <stdio.h>

int main(void) {
    int old = fegetround();
    volatile double one = 1.0;
    volatile double half_ulp = 0x1p-53;
    volatile double down, up;

    if (fesetround(FE_DOWNWARD) != 0) return 2;
    down = one + half_ulp;
    if (fesetround(FE_UPWARD) != 0) return 3;
    up = one + half_ulp;
    fesetround(old);

    if (!(down == 1.0 && up > 1.0)) {
        fprintf(stderr, "directed-rounding probe failed: down=%.17g up=%.17g\n",
                (double)down, (double)up);
        return 1;
    }
    printf("directed-rounding probe: PASS\n");
    return 0;
}
