/*
 * example_data.h -- deterministic pseudo-random entries for the examples.
 *
 * Not part of the library.  It exists because the obvious way to fill a
 * matrix without a random number generator, A[i][j] = sin(c0 + i*c1 + j*c2),
 * produces a matrix of rank two whatever its shape: every such row is a
 * fixed linear combination of one sine and one cosine of i.  An example
 * built on that data reports rank 2 for every system and demonstrates
 * nothing.
 *
 * splitmix64 is used instead: same value on every platform, no dependency,
 * and the rows are genuinely independent.
 */
#ifndef AFFINE_BUNDLE_EXAMPLE_DATA_H
#define AFFINE_BUNDLE_EXAMPLE_DATA_H

#include <stdint.h>

static uint64_t ex_mix(uint64_t x)
{
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}

/* Uniform on (-1, 1), determined entirely by the index. */
static double ex_value(uint64_t index)
{
    uint64_t z = ex_mix(index);
    return ((double)(z >> 11) * (1.0 / 9007199254740992.0)) * 2.0 - 1.0;
}

/* Entry (i, j) of a matrix identified by tag. */
static double ex_entry(uint64_t tag, int i, int j)
{
    return ex_value(tag * 0x100000000ULL + (uint64_t)i * 131071ULL + (uint64_t)j);
}

#endif /* AFFINE_BUNDLE_EXAMPLE_DATA_H */
