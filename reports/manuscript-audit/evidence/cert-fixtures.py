"""Exact dyadic rank witnesses for the two regenerated status-profile fixtures."""
import numpy as np

PRIME = 1_000_000_007


def minor_residue(rows):
    matrix = []
    for row in rows:
        entries = []
        for value in row:
            numerator, denominator = float(value).as_integer_ratio()
            entries.append(numerator * pow(denominator, -1, PRIME) % PRIME)
        matrix.append(entries)
    determinant = 1
    for column in range(len(matrix)):
        pivot = next((i for i in range(column, len(matrix)) if matrix[i][column]), None)
        if pivot is None:
            return 0
        if pivot != column:
            matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
            determinant = -determinant
        value = matrix[column][column]
        determinant = determinant * value % PRIME
        inverse = pow(value, -1, PRIME)
        for i in range(column + 1, len(matrix)):
            factor = matrix[i][column] * inverse % PRIME
            matrix[i] = [(x - factor * y) % PRIME
                         for x, y in zip(matrix[i], matrix[column])]
    return determinant % PRIME


rng = np.random.default_rng(3)
A = rng.standard_normal((48, 8))
x = rng.standard_normal(8)
b = A @ x
print(f"numpy={np.__version__} prime={PRIME}")
print("48x8 first 8x8 coefficient minor", minor_residue(A[:8]))
print("48x8 first 9x9 augmented minor", minor_residue(np.column_stack((A[:9], b[:9]))))

rng = np.random.default_rng(17)
base = rng.integers(-8, 9, size=(40, 4)).astype(np.float64)
base[~np.any(base, axis=1), 0] = 1
print("40x6 first 4x4 base minor", minor_residue(base[:4]))
