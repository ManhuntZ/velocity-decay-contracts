"""A later window scored on the 14 Oct cuts. Not a new spec."""

import unittest
from pathlib import Path

from vdc.contract import LinearTerms
from vdc.fit import fit_launches, load_launches
from vdc.freeze import FROZEN_RANK_HIGH, FROZEN_RANK_LOW, frozen_rank
from vdc.sample import mark_launches

ROOT = Path(__file__).resolve().parents[1]


class ThirdWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first = load_launches(str(ROOT / "data" / "launches.json"))
        cls.second = load_launches(str(ROOT / "data" / "launches_b.json"))
        cls.third = load_launches(str(ROOT / "data" / "launches_c.json"))
        cls.terms = LinearTerms()

    def test_the_window_is_later_and_does_not_share_a_mint(self):
        self.assertEqual(len(self.third), 30)
        third_mints = {row["mint"] for row in self.third}
        self.assertEqual(len(third_mints), 30)
        self.assertEqual(third_mints & {row["mint"] for row in self.first}, set())
        self.assertEqual(third_mints & {row["mint"] for row in self.second}, set())
        self.assertTrue(all(row["samples"][0][0] == 0 for row in self.third))
        self.assertGreater(
            min(row["created"] for row in self.third),
            max(row["created"] for row in self.second),
        )
        self.assertEqual(min(row["created"] for row in self.third), 1792051944000)
        self.assertEqual(max(row["created"] for row in self.third), 1792052427000)

    def test_the_pre_registered_order_holds_and_the_level_does_not(self):
        rank = frozen_rank(self.first, self.third, self.terms)
        self.assertEqual(rank.low_cut, FROZEN_RANK_LOW)
        self.assertEqual(rank.high_cut, FROZEN_RANK_HIGH)
        bins = rank.replication
        self.assertEqual(tuple(bin.n for bin in bins), (12, 10, 8))
        self.assertAlmostEqual(bins[0].mean_payoff, -724.7681424733174, places=9)
        self.assertAlmostEqual(bins[0].stderr, 95.70044536199804, places=9)
        self.assertAlmostEqual(bins[1].mean_payoff, -15.997306309194093, places=9)
        self.assertAlmostEqual(bins[1].stderr, 10.338502143402991, places=9)
        self.assertAlmostEqual(bins[2].mean_payoff, 58.231383866872, places=9)
        self.assertAlmostEqual(bins[2].stderr, 15.093931404647538, places=9)
        self.assertLess(bins[0].mean_payoff, bins[1].mean_payoff)
        self.assertLess(bins[1].mean_payoff, bins[2].mean_payoff)
        self.assertLess(bins[0].mean_payoff, 0.0)
        self.assertGreater(bins[2].mean_payoff, 0.0)
        # Same rank, different crash. Not a price for the worst third.
        self.assertLess(bins[0].mean_payoff, rank.reference[0].mean_payoff - 200.0)
        self.assertGreater(bins[0].mean_payoff, -942.85)

    def test_the_order_is_not_an_artifact_of_the_cap(self):
        rank = frozen_rank(self.first, self.third, LinearTerms(cap=1e12))
        bins = rank.replication
        self.assertAlmostEqual(bins[0].mean_payoff, -976.2566214912672, places=9)
        self.assertAlmostEqual(bins[1].mean_payoff, -15.997306309194093, places=9)
        self.assertAlmostEqual(bins[2].mean_payoff, 58.231383866872, places=9)
        self.assertLess(bins[0].mean_payoff, bins[1].mean_payoff)
        self.assertLess(bins[1].mean_payoff, bins[2].mean_payoff)

    def test_the_mean_is_recorded_and_does_not_move_the_spec(self):
        mark = mark_launches(self.third, self.terms)
        self.assertEqual(mark.n, 30)
        self.assertEqual(mark.n_capped, 6)
        self.assertAlmostEqual(mark.mean_payoff, -279.7113233945592, places=9)
        self.assertAlmostEqual(mark.stderr, 77.43970386329003, places=9)
        self.assertAlmostEqual(mark.mean_velocity, -0.4139562095646374, places=9)
        first = mark_launches(self.first, self.terms)
        second = mark_launches(self.second, self.terms)
        self.assertLess(second.mean_payoff, mark.mean_payoff)
        self.assertLess(mark.mean_payoff, first.mean_payoff)
        fitted = fit_launches(self.third)
        self.assertEqual(fitted.half_life, 120.0)
        self.assertAlmostEqual(fitted.strike_per_minute, -0.03987285983348328, places=9)
        by_half_life = {kernel.half_life: kernel for kernel in fitted.kernels}
        self.assertGreater(abs(by_half_life[120.0].t_stat), abs(by_half_life[300.0].t_stat))
        self.assertAlmostEqual(by_half_life[120.0].t_stat, 1.301298067354026, places=9)
        self.assertLess(abs(by_half_life[120.0].t_stat), 2.0)
        self.assertEqual(LinearTerms().half_life, 120.0)
        self.assertAlmostEqual(LinearTerms().strike_per_minute, -0.03364949456289831, places=12)
        self.assertLess(abs(fitted.strike_per_minute - LinearTerms().strike_per_minute), 0.02)


if __name__ == "__main__":
    unittest.main()
