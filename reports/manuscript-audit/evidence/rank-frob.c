/* Compile from the repository root with -Isrc and the strict guard flags.
 * Link system BLAS and LAPACK as in the report. No production source changes. */
#include <stdio.h>
#include "formation_guard.c"

int main(void) {
    if (LDBL_MANT_DIG != 64) {
        puts("This input targets a 64-bit long-double significand.");
        return 77;
    }
    const size_t count = 20000001;
    double *entries = malloc(count * sizeof(*entries));
    if (!entries) return 2;
    entries[0] = 1.0;
    for (size_t i = 1; i < count; ++i) entries[i] = 0x1p-32;
    const double bound = frob_up(entries, count);
    free(entries);
    /* 1 + 20,000,000 * 2^-64 is exactly representable in this format.
     * The comparison has a gap of several hundred binary64 ulps. */
    const long double exact_square = 1.0L + (count - 1) * 0x1p-64L;
    printf("count=%zu LDBL_MANT_DIG=%d bound=%a exact_square=%La\n"
           "bound_squared_minus_exact_square=%.21Lg\n",
           count, LDBL_MANT_DIG, bound, exact_square,
           (long double)bound * bound - exact_square);
    return 0;
}
