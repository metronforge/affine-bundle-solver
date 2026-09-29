/* Test-only interception, independent of ELF/GNU --wrap. The wrapper calls
 * the real BLAS; the production translation unit is otherwise unchanged. */
#include "blas_symbols.h"
#undef dgeqp3_
#define dgeqp3_ abs_test_dgeqp3
#include "../src/certified_api.c"
