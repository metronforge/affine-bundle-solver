/* Include the pinned translation unit to exercise its private norm helper. */
#include "status_certificate.c"
#include <float.h>
#include <stdio.h>

int main(void) {
    double negative[] = {2, -DBL_TRUE_MIN};
    double positive[] = {2, DBL_TRUE_MIN};
    printf("negative norm_upper=%a\n", norm_up(negative, 2));
    printf("positive norm_upper=%a\n", norm_up(positive, 2));
    return 0;
}
