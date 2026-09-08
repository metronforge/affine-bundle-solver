/*
 * blas_symbols.h -- which BLAS/LAPACK symbols this build calls.
 *
 * Internal header.  Not installed.
 *
 * SciPy ships its own OpenBLAS inside the wheel and renames every exported
 * Fortran symbol with a scipy_ prefix, so that a process which also loads a
 * system BLAS cannot end up with two different implementations answering to
 * the same name.  The solver was developed against that library, so the
 * prefixed names were written directly into the sources.
 *
 * The consequence was that the C code, and not just the build script, could
 * only ever link against SciPy's copy: a system BLAS exports dgelsy_ and
 * knows nothing about scipy_dgelsy_.  Building the library therefore required
 * a Python installation carrying a SciPy wheel, which is a strange thing to
 * ask of someone who wants to link a C library.
 *
 * The prefix is now a build-time choice and nothing else:
 *
 *   -DABS_SCIPY_BLAS   call SciPy's OpenBLAS.  This is what build.sh does,
 *                      and it is what reproduces the manuscript.
 *   (not defined)      call whatever BLAS and LAPACK the linker is given,
 *                      under the ordinary Fortran ABI names.
 *
 * With ABS_SCIPY_BLAS defined the preprocessor output is identical to what it
 * was before this header existed, so the numbers in the manuscript are
 * unaffected by its introduction.
 *
 * Note that the choice is not purely cosmetic in the other direction.  A
 * different BLAS sums in a different order, and the router classifies by
 * comparing computed quantities against thresholds, so a borderline system
 * can in principle land on the other side of a rank threshold.  That is a
 * measurement, not an assumption: tests/compare_builds.py compares two builds
 * on exactly the fields the manuscript makes claims about.
 */
#ifndef AFFINE_BUNDLE_BLAS_SYMBOLS_H
#define AFFINE_BUNDLE_BLAS_SYMBOLS_H

#ifdef ABS_SCIPY_BLAS

#define dgecon_ scipy_dgecon_
#define dgels_  scipy_dgels_
#define dgelsy_ scipy_dgelsy_
#define dgemm_  scipy_dgemm_
#define dgemv_  scipy_dgemv_
#define dgeqp3_ scipy_dgeqp3_
#define dgeqrf_ scipy_dgeqrf_
#define dgesvd_ scipy_dgesvd_
#define dgetrf_ scipy_dgetrf_
#define dgetrs_ scipy_dgetrs_
#define dorgqr_ scipy_dorgqr_
#define dormqr_ scipy_dormqr_
#define dtrcon_ scipy_dtrcon_
#define dtrtri_ scipy_dtrtri_

#endif /* ABS_SCIPY_BLAS */

#endif /* AFFINE_BUNDLE_BLAS_SYMBOLS_H */
