import unittest
from pathlib import Path

from vdc.contract import LinearTerms
from vdc.fit import load_launches
from vdc.sample import mark_launches

ROOT = Path(__file__).resolve().parents[1]


class SampleMarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.launches = load_launches(str(ROOT / "data" / "launches.json"))

    def test_default_terms_match_the_locked_mark(self):
        mark = mark_launches(self.launches, LinearTerms())
        self.assertEqual(mark.n, 33)
        self.assertEqual(mark.n_capped, 1)
        self.assertAlmostEqual(mark.mean_payoff, -131.132307299713, places=9)
        self.assertAlmostEqual(mark.stderr, 56.176325608762, places=9)
        self.assertAlmostEqual(mark.mean_velocity, -0.169646076968, places=9)

    def test_a_higher_strike_pays_the_long_less(self):
        base = mark_launches(self.launches, LinearTerms())
        higher = mark_launches(self.launches, LinearTerms(strike_per_minute=0.0))
        self.assertLess(higher.mean_payoff, base.mean_payoff)

    def test_thirty_minute_window_is_not_this_sample(self):
        with self.assertRaises(ValueError):
            mark_launches(self.launches, LinearTerms(window=1800.0))


if __name__ == "__main__":
    unittest.main()
