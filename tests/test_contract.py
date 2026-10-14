import math
import unittest

from vdc.contract import DigitalTerms, LinearTerms, settle_digital, settle_linear
from vdc.curve import QUOTE0, TOKEN0, path_from_trades
from vdc.scenarios import SCENARIOS


def _samples(name: str, window: float = 900.0):
    prints = path_from_trades(QUOTE0, TOKEN0, SCENARIOS[name](), window)
    return [(p.t, p.price) for p in prints]


class ContractTests(unittest.TestCase):
    def test_same_multiple_different_velocity(self):
        terms = LinearTerms(strike_per_minute=0.0, notional=1.0, cap=10.0)
        settled = {name: settle_linear(_samples(name), terms) for name in ("sniper", "grind", "late")}
        self.assertAlmostEqual(settled["sniper"].price_end, settled["late"].price_end, places=12)
        self.assertAlmostEqual(
            settled["sniper"].log_slope_per_minute,
            settled["late"].log_slope_per_minute,
            places=12,
        )
        self.assertAlmostEqual(
            settled["sniper"].arithmetic_slope_per_minute,
            settled["grind"].arithmetic_slope_per_minute,
            places=12,
        )
        self.assertGreater(settled["sniper"].velocity_per_minute, settled["grind"].velocity_per_minute)
        self.assertGreater(settled["grind"].velocity_per_minute, settled["late"].velocity_per_minute)

    def test_flat_kernel_collapses_the_three_paths(self):
        terms = LinearTerms(half_life=math.inf, strike_per_minute=0.0, notional=1.0, cap=10.0)
        vs = [settle_linear(_samples(name), terms).velocity_per_minute for name in ("sniper", "grind", "late")]
        self.assertAlmostEqual(vs[0], vs[1], places=12)
        self.assertAlmostEqual(vs[1], vs[2], places=12)

    def test_payoff_is_capped_at_collateral(self):
        samples = [(0.0, 1.0), (1.0, math.e), (900.0, math.e)]
        terms = LinearTerms(strike_per_minute=0.0, notional=1000.0, cap=100.0, half_life=300.0)
        settled = settle_linear(samples, terms)
        self.assertEqual(settled.payoff_to_long, 100.0)
        self.assertTrue(settled.capped)

    def test_short_is_the_other_side_of_the_cap(self):
        samples = [(0.0, 1.0), (900.0, 1.0)]
        terms = LinearTerms(strike_per_minute=0.05, notional=1000.0, cap=250.0)
        settled = settle_linear(samples, terms)
        self.assertGreaterEqual(settled.payoff_to_long, -terms.cap)
        self.assertLessEqual(settled.payoff_to_long, terms.cap)
        self.assertLess(settled.payoff_to_long, 0.0)

    def test_digital_is_zero_sum_and_struck(self):
        dead = [(0.0, 1.0), (900.0, 1.0)]
        hot = [(0.0, 1.0), (1.0, math.e), (900.0, math.e)]
        terms = DigitalTerms(strike_per_minute=0.02, premium=0.35, payout=1.0)
        miss = settle_digital(dead, terms)
        hit = settle_digital(hot, terms)
        self.assertFalse(miss.hit)
        self.assertTrue(hit.hit)
        self.assertAlmostEqual(miss.long_pnl + miss.short_pnl, 0.0, places=12)
        self.assertAlmostEqual(hit.long_pnl + hit.short_pnl, 0.0, places=12)
        self.assertAlmostEqual(miss.long_pnl, -0.35, places=12)
        self.assertAlmostEqual(hit.long_pnl, 0.65, places=12)

    def test_premium_outside_the_payout_is_rejected(self):
        with self.assertRaises(ValueError):
            DigitalTerms(premium=1.0, payout=1.0)


if __name__ == "__main__":
    unittest.main()
