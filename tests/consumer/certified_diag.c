#include <affine_bundle/certified_api.h>
#include <stddef.h>

_Static_assert(ABS_OUT_LEN == 11, "unexpected router meta layout");
_Static_assert(sizeof(BSCertifiedResult) == 112, "legacy ABI changed");
_Static_assert(offsetof(BSCombinedCertifiedResult, router_meta) == sizeof(BSCertifiedResult),
               "combined prefix changed");
_Static_assert(offsetof(BSCombinedCertifiedResult, grey_rows) == 208, "grey offset changed");
_Static_assert(offsetof(BSCombinedCertifiedResult, formation_guard_counters) == 488,
               "guard offset changed");
_Static_assert(sizeof(BSCombinedCertifiedResult) == 512, "combined ABI size changed");

int main(void)
{
    const double A[]={1,0,0,1}, b[]={2,3};
    BSCombinedCertifiedResult result;
    return bsolve_certified_diag_api(A,b,NULL,2,2,1,2,2,7,0,&result) ||
           result.router_meta[ABS_OUT_STATUS] != ABS_STATUS_UNIQUE;
}
