"""The 15 Oct window is a replication, not a new spec."""

import unittest
from pathlib import Path

from vdc.contract import LinearTerms
from vdc.fit import fit_launches, load_launches
from vdc.sample import mark_launches

ROOT = Path(__file__).resolve().parents[1]


class SecondWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first = load_launches(str(ROOT / "data" / "launches.json"))
        cls.second = load_launches(str(ROOT / "data" / "launches_b.json"))

    def test_the_windows_do_not_share_a_mint(self):
        self.assertEqual(len(self.second), 30)
        self.assertEqual(
            {row["mint"] for row in self.first} & {row["mint"] for row in self.second},
            set(),
        )

    def test_two_minutes_still_wins_and_the_strike_barely_moves(self):
        fitted = fit_launches(self.second)
        self.assertEqual(fitted.half_life, 120.0)
        self.assertAlmostEqual(fitted.strike_per_minute, -0.0446862810517755, places=9)
        by_half_life = {kernel.half_life: kernel for kernel in fitted.kernels}
        self.assertGreater(abs(by_half_life[120.0].t_stat), abs(by_half_life[300.0].t_stat))
        self.assertGreater(abs(by_half_life[300.0].t_stat), abs(by_half_life[600.0].t_stat))
        self.assertGreater(abs(by_half_life[600.0].t_stat), 0.0)
        # One point per minute is not a new contract. The locked strike stays.
        self.assertLess(abs(fitted.strike_per_minute - LinearTerms().strike_per_minute), 0.02)
        self.assertEqual(LinearTerms().half_life, 120.0)
        self.assertAlmostEqual(LinearTerms().strike_per_minute, -0.03364949456289831, places=12)

    def test_the_mean_does_not_replicate(self):
        mark = mark_launches(self.second, LinearTerms())
        self.assertEqual(mark.n, 30)
        self.assertEqual(mark.n_capped, 10)
        self.assertAlmostEqual(mark.mean_payoff, -363.591984849986, places=9)
        self.assertAlmostEqual(mark.stderr, 91.956532876342, places=9)
        self.assertAlmostEqual(mark.mean_velocity, -0.585203101302, places=9)
        first = mark_launches(self.first, LinearTerms())
        self.assertLess(mark.mean_payoff, first.mean_payoff - 100.0)


if __name__ == "__main__":
    unittest.main()
