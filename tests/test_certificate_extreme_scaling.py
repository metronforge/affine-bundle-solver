"""Apple ARM64 long double must not narrow unique-witness input range."""
import math
import numpy as np
from pbt_equivalence_orbits import certified

# This is the existing property battery's extreme-scaling fixture, made a
# required regression after macOS exposed row_norm's extended-range assumption.
A = np.array([[1., 0.], [0., 1.], [1., 1.], [2., -1.]])
x = np.array([2., -3.])
b = A @ x
for exponent in (-1000, -800, -600, -537, -530, -500, -400, -200, 0, 200, 400, 500, 600, 800, 1000):
    result = certified(np.ldexp(A, exponent), np.ldexp(b, exponent), x, 777)
    assert result["mask"] & 1, (exponent, result)
    assert math.isfinite(result["eta_unique"]) and result["eta_unique"] < 1e-10, (exponent, result)
print("unique witness extreme binary scaling: PASS (15 scales)")
