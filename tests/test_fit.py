import math
import unittest
from pathlib import Path

from vdc.contract import LinearTerms
from vdc.curve import QUOTE0, TOKEN0, path_from_trades
from vdc.fit import HALF_LIVES, fit_launches, load_launches, time_reversed
from vdc.scenarios import SCENARIOS
from vdc.velocity import decay_weighted_velocity

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "launches.json"


def _gap(samples, window, half_life) -> float:
    forward = decay_weighted_velocity(samples, window, half_life).per_minute
    backward = decay_weighted_velocity(time_reversed(samples, window), window, half_life).per_minute
    return forward - backward


class FitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.launches = load_launches(str(SAMPLE))
        cls.fit = fit_launches(cls.launches)

    def test_sample_is_the_shipped_window(self):
        self.assertEqual(len(self.launches), 33)
        self.assertTrue(SAMPLE.is_file())

    def test_time_reversal_picks_two_minutes(self):
        self.assertEqual(self.fit.n, 33)
        self.assertEqual(self.fit.half_life, 120.0)
        by_half_life = {kernel.half_life: kernel for kernel in self.fit.kernels}
        self.assertEqual(set(by_half_life), set(HALF_LIVES))
        self.assertGreater(abs(by_half_life[120.0].t_stat), abs(by_half_life[300.0].t_stat))
        self.assertGreater(abs(by_half_life[300.0].t_stat), abs(by_half_life[600.0].t_stat))
        self.assertGreater(abs(by_half_life[600.0].t_stat), abs(by_half_life[math.inf].t_stat))
        self.assertEqual(by_half_life[math.inf].t_stat, 0.0)
        self.assertLess(abs(by_half_life[math.inf].mean_gap), 1e-9)

    def test_strike_is_the_sixtieth_percentile_and_the_default(self):
        terms = LinearTerms()
        self.assertEqual(terms.half_life, 120.0)
        self.assertAlmostEqual(self.fit.strike_per_minute, -0.03364949456289831, places=12)
        self.assertAlmostEqual(terms.strike_per_minute, self.fit.strike_per_minute, places=12)
        self.assertAlmostEqual(self.fit.hit_rate, 13 / 33, places=12)

    def test_tapes_that_moved_keep_the_same_ranking(self):
        moved = []
        for launch in self.launches:
            samples = [(float(t), float(price)) for t, price in launch["samples"]]
            if abs(decay_weighted_velocity(samples, 900.0, math.inf).log_return) >= 0.2:
                moved.append(launch)
        self.assertEqual(len(moved), 26)
        fitted = fit_launches(moved)
        ordered = [kernel.half_life for kernel in sorted(fitted.kernels, key=lambda kernel: abs(kernel.t_stat), reverse=True)]
        self.assertEqual(ordered, [120.0, 300.0, 600.0, math.inf])

    def test_reversing_the_sniper_tape_moves_the_decay_kernel_only(self):
        prints = path_from_trades(QUOTE0, TOKEN0, SCENARIOS["sniper"](), 900.0)
        samples = [(print_.t, print_.price) for print_ in prints]
        gap_decay = _gap(samples, 900.0, 120.0)
        gap_flat = _gap(samples, 900.0, math.inf)
        self.assertGreater(gap_decay, 0.0)
        self.assertAlmostEqual(gap_flat, 0.0, places=9)
        self.assertGreater(gap_decay, abs(gap_flat))


if __name__ == "__main__":
    unittest.main()
