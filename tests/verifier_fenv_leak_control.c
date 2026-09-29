/* Compile the real verifier with only its rounding-restoration behavior
 * deliberately broken. This source is never included in installed libraries. */
#include <fenv.h>
static int leak_nearest(int mode) {
    return fesetround(mode == FE_TONEAREST ? FE_UPWARD : mode);
}
#define fesetround leak_nearest
#include "../src/status_certificate.c"
