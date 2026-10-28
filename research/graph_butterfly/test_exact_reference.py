"""Small exact regression cases for research interface composition."""
import unittest
from exact_reference import interface_feasible, interface_feasible_incremental


class InterfaceTests(unittest.TestCase):
    def check_both(self, left, right, nl, nr, ns, expected):
        self.assertEqual(interface_feasible(left, right, nl, nr, ns), expected)
        self.assertEqual(interface_feasible_incremental(left, right, nl, nr, ns), expected)

    def test_consistent_shared_interface(self):
        # u=s and v=s; arbitrary shared s is feasible.
        self.check_both([[1, -1, 0]], [[1, -1, 0]], 1, 1, 1, True)

    def test_conflicting_interface(self):
        # Each block constrains s, with incompatible RHS.
        self.check_both([[0, 1, 0]], [[0, 1, 1]], 1, 1, 1, False)

    def test_conflict_hidden_by_internal_elimination(self):
        # u=0, u=s forces s=0; v=1, v=s forces s=1.
        self.check_both([[1, 0, 0], [1, -1, 0]],
                        [[1, 0, 1], [1, -1, 0]], 1, 1, 1, False)

    def test_free_internal(self):
        self.check_both([[1, 1, 2]], [[1, -1, 3]], 1, 1, 1, True)


if __name__ == "__main__":
    unittest.main()
