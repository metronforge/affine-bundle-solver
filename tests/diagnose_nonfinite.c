/* Diagnostic control for compilers folding bit-based finite checks under
 * fast math. Build fast and link without fast math. No solver code changes. */
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

static int by_value(double x) {
    uint64_t u; memcpy(&u, &x, sizeof u);
    return (int)(((u >> 52) & 0x7ffu) == 0x7ffu);
}
static int by_pointer(const double *x) {
    uint64_t u; memcpy(&u, x, sizeof u);
    return (int)(((u >> 52) & 0x7ffu) == 0x7ffu);
}
static int volatile_bits(double x) {
    uint64_t u; memcpy(&u, &x, sizeof u);
    volatile uint64_t observed = u;
    return (int)(((observed >> 52) & 0x7ffu) == 0x7ffu);
}
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    uint64_t u;
    if (sscanf(argv[1], "%" SCNx64, &u) != 1) return 2;
    double x; memcpy(&x, &u, sizeof x);
    printf("bits=%llx by_value=%d by_pointer=%d volatile_bits=%d sizeof(long double)=%zu\n",
           (unsigned long long)u, by_value(x), by_pointer(&x), volatile_bits(x), sizeof(long double));
    return 0;
}
