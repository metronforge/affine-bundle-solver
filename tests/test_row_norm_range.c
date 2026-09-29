/* Test the actual private helper under every caller rounding mode. */
#include <fenv.h>
#include <stdio.h>
#include "../src/certified_api.c"

int main(void) {
    const int modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
    const int exponents[] = {-1074, -1000, -600, -537, -530, 0, 600, 1000, 1023};
    int original = fegetround(), failed = 0;
    for (size_t mode = 0; mode < sizeof modes / sizeof modes[0]; ++mode) {
        if (fesetround(modes[mode])) return 2;
        for (size_t e = 0; e < sizeof exponents / sizeof exponents[0]; ++e) {
            double expected = scalbn(1.0, exponents[e]);
            double a[2] = {-expected, 0.0};
            double actual = row_norm(a, 2);
            if (actual != expected || fegetround() != modes[mode]) {
                fprintf(stderr, "norm range mode=%d exponent=%d actual=%a expected=%a\n",
                        modes[mode], exponents[e], actual, expected);
                failed = 1;
            }
        }
    }
    if (fesetround(original)) return 2;
    if (!failed) puts("private row norm: exact powers across full binary64 range and four rounding modes PASS");
    return failed;
}
