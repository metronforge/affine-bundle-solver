"""Contract test for the opt-in fast-router scalar control build."""

from pathlib import Path
import unittest


class RouterNoAutovecConfigTest(unittest.TestCase):
    def test_control_option_is_scoped_to_router_objects(self):
        cmake = Path(__file__).resolve().parents[1] / "CMakeLists.txt"
        text = cmake.read_text()
        self.assertIn("ABS_DISABLE_ROUTER_AUTOVECTORIZATION", text)
        self.assertIn("-fno-tree-vectorize", text)
        self.assertIn("-fno-tree-slp-vectorize", text)

        router = text.index("add_library(abs_router_obj OBJECT src/bsolver.c)")
        strict = text.index("add_library(status_verifier SHARED src/status_certificate.c)")
        control = text.index("ABS_ROUTER_AUTOVEC_CONTROL_FLAGS")
        self.assertLess(control, router)
        self.assertLess(router, strict)
        strict_block = text[strict:text.index("add_library(certified_solver", strict)]
        self.assertNotIn("ABS_ROUTER_AUTOVEC_CONTROL_FLAGS", strict_block)


if __name__ == "__main__":
    unittest.main()
