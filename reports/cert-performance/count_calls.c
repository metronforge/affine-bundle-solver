/* Linux diagnostic build only. Count dynamically linked calls during one certificate. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fenv.h>
#include <stdint.h>
#include <string.h>

static _Thread_local int enabled;
static _Thread_local uint64_t events[3];
static int (*real_setround)(int);
static double (*real_frexp)(double, int *);
static double (*real_scalbn)(double, int);

__attribute__((constructor)) static void bind_functions(void) {
    real_setround = dlsym(RTLD_NEXT, "fesetround");
    real_frexp = dlsym(RTLD_NEXT, "frexp");
    real_scalbn = dlsym(RTLD_NEXT, "scalbn");
}

void start_counts(void) {
    memset(events, 0, sizeof events);
    enabled = 1;
}

void stop_counts(uint64_t *out) {
    enabled = 0;
    memcpy(out, events, sizeof events);
}

int fesetround(int mode) {
    if (enabled) ++events[0];
    return real_setround(mode);
}

double frexp(double value, int *exponent) {
    if (enabled) ++events[1];
    return real_frexp(value, exponent);
}

double scalbn(double value, int exponent) {
    if (enabled) ++events[2];
    return real_scalbn(value, exponent);
}
