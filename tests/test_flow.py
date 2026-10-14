import unittest

from vdc.contract import LinearTerms
from vdc.curve import QUOTE0, TOKEN0
from vdc.flow import FRONT_LOADED, monte_carlo_linear


class FlowTests(unittest.TestCase):
    def test_mark_is_reproducible_and_inside_the_cap(self):
        terms = LinearTerms(window=FRONT_LOADED.window)
        a = monte_carlo_linear(QUOTE0, TOKEN0, FRONT_LOADED, terms, n=40, seed=7)
        b = monte_carlo_linear(QUOTE0, TOKEN0, FRONT_LOADED, terms, n=40, seed=7)
        self.assertEqual(a.fair_to_long, b.fair_to_long)
        self.assertEqual(a.mean_velocity, b.mean_velocity)
        self.assertGreaterEqual(a.fair_to_long, -terms.cap)
        self.assertLessEqual(a.fair_to_long, terms.cap)
        self.assertGreater(a.stderr, 0.0)

    def test_window_mismatch_rejected(self):
        terms = LinearTerms(window=1800.0)
        with self.assertRaises(ValueError):
            monte_carlo_linear(QUOTE0, TOKEN0, FRONT_LOADED, terms, n=4, seed=1)


if __name__ == "__main__":
    unittest.main()
