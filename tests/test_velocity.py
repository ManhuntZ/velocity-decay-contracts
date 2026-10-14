import math
import unittest

from vdc.velocity import (
    arithmetic_slope_per_minute,
    decay_weighted_velocity,
    log_slope_per_minute,
)


class VelocityTests(unittest.TestCase):
    def test_uniform_kernel_matches_log_slope(self):
        samples = [(0.0, 1.0), (300.0, 2.0), (900.0, math.e)]
        weighted = decay_weighted_velocity(samples, 900.0, math.inf)
        self.assertAlmostEqual(weighted.per_minute, 60.0 / 900.0, places=12)
        self.assertAlmostEqual(weighted.per_minute, log_slope_per_minute(samples, 900.0), places=12)

    def test_early_print_outranks_late_print(self):
        early = [(0.0, 1.0), (1.0, math.e), (900.0, math.e)]
        late = [(0.0, 1.0), (899.0, 1.0), (900.0, math.e)]
        v_early = decay_weighted_velocity(early, 900.0, 300.0).per_minute
        v_late = decay_weighted_velocity(late, 900.0, 300.0).per_minute
        self.assertGreater(v_early, v_late)
        # Same total log return, so a flat kernel cannot tell them apart.
        self.assertAlmostEqual(
            decay_weighted_velocity(early, 900.0, math.inf).per_minute,
            decay_weighted_velocity(late, 900.0, math.inf).per_minute,
            places=12,
        )

    def test_flat_carry_dilutes(self):
        stopped = [(0.0, 1.0), (60.0, 2.0)]
        held = [(0.0, 1.0), (60.0, 2.0), (900.0, 2.0)]
        a = decay_weighted_velocity(stopped, 900.0, 300.0)
        b = decay_weighted_velocity(held, 900.0, 300.0)
        self.assertAlmostEqual(a.per_minute, b.per_minute, places=12)
        self.assertAlmostEqual(a.log_return, math.log(2.0), places=12)

    def test_prints_after_expiry_do_not_count(self):
        inside = decay_weighted_velocity([(0.0, 1.0), (100.0, 2.0)], 900.0, 300.0)
        leaked = decay_weighted_velocity(
            [(0.0, 1.0), (100.0, 2.0), (5000.0, 100.0)],
            900.0,
            300.0,
        )
        self.assertAlmostEqual(inside.per_minute, leaked.per_minute, places=12)
        self.assertAlmostEqual(leaked.price_end, 2.0, places=12)

    def test_anchor_required(self):
        with self.assertRaises(ValueError):
            decay_weighted_velocity([(1.0, 1.0), (10.0, 2.0)], 900.0, 300.0)

    def test_non_positive_price_rejected(self):
        with self.assertRaises(ValueError):
            decay_weighted_velocity([(0.0, 0.0), (10.0, 1.0)], 900.0, 300.0)

    def test_sketch_slope_is_arithmetic_not_log(self):
        samples = [(0.0, 1.0), (900.0, 2.0)]
        arith = arithmetic_slope_per_minute(samples, 900.0)
        log_slope = log_slope_per_minute(samples, 900.0)
        self.assertAlmostEqual(arith, 1.0 / 15.0, places=12)
        self.assertGreater(arith, log_slope)

    def test_duplicate_timestamp_last_price_wins(self):
        v = decay_weighted_velocity([(0.0, 1.0), (0.0, 2.0), (900.0, 2.0)], 900.0, math.inf)
        self.assertAlmostEqual(v.per_minute, 0.0, places=12)
        self.assertAlmostEqual(v.price_start, 2.0, places=12)


if __name__ == "__main__":
    unittest.main()
