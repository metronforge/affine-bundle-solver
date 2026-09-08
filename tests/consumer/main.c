/* Consumes the installed interface only: no path into src/, no Python. */
#include <stdio.h>
#include <math.h>
#include <affine_bundle/router.h>

int main(void)
{
    enum { M = 120, N = 5 };
    static double A[M * N], b[M];
    double out[ABS_OUT_LEN];
    int i, j;

    for (i = 0; i < M; i++) {
        double s = 0.0;
        for (j = 0; j < N; j++) {
            A[i * N + j] = sin(1.0 + i * 0.31 + j * 0.77);
            s += A[i * N + j] * (j + 1);
        }
        b[i] = s;
    }
    bsolve_router_meta_api(A, b, NULL, M, N, 1, 2, 2, 7ULL, 0, out);

    printf("status=%d cls=%d rank=%d interval=[%d,%d]\n",
           (int)out[ABS_OUT_STATUS], (int)out[ABS_OUT_CLS],
           (int)out[ABS_OUT_RANK],
           (int)out[ABS_OUT_RANK_LO], (int)out[ABS_OUT_RANK_HI]);

    /* The last two columns are linearly independent by construction and
       M >> N, so anything other than a consistent classification here means
       the installed library is not the one that was tested. */
    if ((int)out[ABS_OUT_STATUS] != ABS_STATUS_UNIQUE &&
        (int)out[ABS_OUT_STATUS] != ABS_STATUS_INFINITE) {
        fprintf(stderr, "unexpected status from an installed library\n");
        return 1;
    }
    return 0;
}
