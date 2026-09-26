/* Tall full-rank audits need one source least-squares witness for UNIQUE and
   INFINITE; the independent INCONSISTENT profile still solves its normalized
   system. The combined API must therefore make exactly two source solves. */
#include <affine_bundle/certified_api.h>
#include <stdio.h>

static unsigned long calls;
void abs_test_certified_lstsq_hook(void) { ++calls; }

int main(void)
{
    const double A[] = {1,0, 0,1, 1,1};
    const double b[] = {2,3,5};
    BSCombinedCertifiedResult out;
    if (bsolve_certified_diag_api(A,b,NULL,3,2,1,2,2,17,0,&out) ||
        calls != 2 || out.certified.fast_status != ABS_STATUS_UNIQUE) {
        fprintf(stderr,"combined audit least-squares calls=%lu status=%d\n",
                calls,out.certified.fast_status);
        return 1;
    }
    puts("combined audit least-squares reuse: PASS");
    return 0;
}
