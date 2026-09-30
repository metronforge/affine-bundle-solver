/* Test-only trace for the combined INFINITE generator.  The installed ABI is
   unchanged: hooks exist only in this separately compiled test target. */
#include <affine_bundle/certified_api.h>

#include <stdio.h>
#include <math.h>

/* Test-local entry point: the production helper remains private. */
extern int abs_test_smallest_subspace_vector(const double *, const double *, int, int, double *);

static int check_rotated_cluster(void)
{
    const double s[] = {4,1,1};
    const double base[] = {0,1,0, 0,0,1, 1,0,0}; /* column-major VT */
    double expected[3], actual[3];
    if(abs_test_smallest_subspace_vector(s,base,3,3,expected))return 1;
    if(fabs(expected[0]-1)>1e-14 || fabs(expected[1])>1e-14 || fabs(expected[2])>1e-14)return 1;
    for(int t=0;t<17;t++){
        double angle=0.19*t,c=cos(angle),sn=sin(angle),vt[9];
        for(int j=0;j<3;j++){
            vt[3*j]=base[3*j];
            vt[3*j+1]=c*base[3*j+1]+sn*base[3*j+2];
            vt[3*j+2]=-sn*base[3*j+1]+c*base[3*j+2];
        }
        if(abs_test_smallest_subspace_vector(s,vt,3,3,actual))return 1;
        for(int j=0;j<3;j++)if(fabs(actual[j]-expected[j])>1e-14){
            fprintf(stderr,"rotated cluster changed proposal: angle=%g coordinate=%d\n",angle,j);
            return 1;
        }
    }
    /* A separated minimum must retain its own direction. */
    const double separated[]={4,2,1};
    if(abs_test_smallest_subspace_vector(separated,base,3,3,actual))return 1;
    if(fabs(actual[1]-1)>1e-14 || fabs(actual[0])>1e-14 || fabs(actual[2])>1e-14)return 1;
    /* A 1x3 matrix has two implicit zero singular values in full VT. */
    if(abs_test_smallest_subspace_vector(separated,base,1,3,actual))return 1;
    if(fabs(actual[0]-1)>1e-14 || fabs(actual[1])>1e-14 || fabs(actual[2])>1e-14)return 1;
    const double zero[]={0,0,0};
    if(abs_test_smallest_subspace_vector(zero,base,3,3,actual))return 1;
    if(fabs(actual[0]-1)>1e-14 || fabs(actual[1])>1e-14 || fabs(actual[2])>1e-14)return 1;
    return 0;
}

enum { QRCP_START = 1, QRCP_VERIFY = 2, DGESDD_START = 3, DGESDD_VERIFY = 4 };
static int event_count[5];
static int force_qrcp_reject;

void abs_test_infinite_fastpath_hook(int event)
{
    if (event >= QRCP_START && event <= DGESDD_VERIFY) ++event_count[event];
}

int abs_test_infinite_force_qrcp_reject(void)
{
    return force_qrcp_reject;
}

static int run(const char *name, const double *A, const double *b, int m, int n,
               int require_qrcp_verify, int require_dgesdd)
{
    BSCombinedCertifiedResult out;
    if (bsolve_certified_diag_api(A, b, NULL, m, n, 1, 2, 2, 17, 0, &out)) {
        fprintf(stderr, "%s: combined API failed\n", name);
        return 1;
    }
    if (event_count[QRCP_START] != 1 ||
        (!!event_count[QRCP_VERIFY] != !!require_qrcp_verify) ||
        (!!event_count[DGESDD_START] != !!require_dgesdd) ||
        (!!event_count[DGESDD_VERIFY] != !!require_dgesdd)) {
        fprintf(stderr, "%s: qrcp=%d/%d dgesdd=%d/%d require=%d\n", name,
                event_count[QRCP_START], event_count[QRCP_VERIFY],
                event_count[DGESDD_START], event_count[DGESDD_VERIFY], require_dgesdd);
        return 1;
    }
    return 0;
}

int main(void)
{
    if(check_rotated_cluster())return 1;
    const double deficient_A[] = {1,0, 2,0, 3,0};
    const double deficient_b[] = {2,4,6};
    const double full_A[] = {1,0, 0,1};
    const double full_b[] = {2,3};

    force_qrcp_reject = 0;
    if (run("accepted-qrcp", deficient_A, deficient_b, 3, 2, 1, 0)) return 1;
    for (int i = 0; i < 5; ++i) event_count[i] = 0;
    force_qrcp_reject = 1;
    if (run("forced-qrcp-rejection", deficient_A, deficient_b, 3, 2, 1, 1)) return 1;
    for (int i = 0; i < 5; ++i) event_count[i] = 0;
    force_qrcp_reject = 0;
    if (run("qrcp-unavailable", full_A, full_b, 2, 2, 0, 1)) return 1;
    puts("combined INFINITE QRCP -> strict verifier -> DGESDD fallback: PASS");
    return 0;
}
