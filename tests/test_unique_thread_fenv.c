/* OpenMP workers must not share directed-rounding or MXCSR state.  This is a
   focused platform probe for the strict UNIQUE outer-row parallelization. */
#include <fenv.h>
#include <omp.h>
#include <stdint.h>
#include <stdio.h>

#if defined(__SSE__)
#include <xmmintrin.h>
#endif

enum { WORKERS = 8 };

int main(void)
{
    int failures = 0;
#pragma omp parallel num_threads(WORKERS) reduction(+:failures)
    {
        int tid = omp_get_thread_num();
        int saved_round = fegetround();
#if defined(__SSE__)
        unsigned saved_mxcsr = _mm_getcsr();
#endif
        int requested = (tid & 1) ? FE_UPWARD : FE_DOWNWARD;
        if (fesetround(requested) != 0 || fegetround() != requested) ++failures;
#if defined(__SSE__)
        /* Bits 13--14 are the MXCSR rounding-control field. */
        unsigned requested_mxcsr = (saved_mxcsr & ~(3u << 13)) |
            ((unsigned)((tid & 1) ? 2 : 1) << 13);
        _mm_setcsr(requested_mxcsr);
        if ((_mm_getcsr() & (3u << 13)) != (requested_mxcsr & (3u << 13))) ++failures;
#endif
#pragma omp barrier
        if (fegetround() != requested) ++failures;
#if defined(__SSE__)
        if ((_mm_getcsr() & (3u << 13)) != (requested_mxcsr & (3u << 13))) ++failures;
        _mm_setcsr(saved_mxcsr);
#endif
        if (fesetround(saved_round) != 0 || fegetround() != saved_round) ++failures;
    }
    if (failures) {
        fprintf(stderr, "thread-local fenv/MXCSR isolation failures=%d\n", failures);
        return 1;
    }
    puts("parallel worker fenv/MXCSR isolation: PASS");
    return 0;
}
