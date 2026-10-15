"""Flat-carry at a clock, against the finished tape. Not a new spec."""

import unittest
from pathlib import Path

from vdc.contract import LinearTerms, settle_linear
from vdc.curve import QUOTE0, TOKEN0, path_from_trades
from vdc.fit import load_launches
from vdc.freeze import (
    FROZEN_RANK_HIGH,
    FROZEN_RANK_LOW,
    freeze_clock,
    frozen_rank,
    frozen_velocity,
    tertile_edges,
    window_gap,
)
from vdc.sample import mark_launches
from vdc.scenarios import late_trades

ROOT = Path(__file__).resolve().parents[1]


class FreezeClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first = load_launches(str(ROOT / "data" / "launches.json"))
        cls.second = load_launches(str(ROOT / "data" / "launches_b.json"))
        cls.terms = LinearTerms()
        cls.a = {point.clock: point for point in freeze_clock(cls.first, cls.terms)}
        cls.b = {point.clock: point for point in freeze_clock(cls.second, cls.terms)}

    def test_two_minutes_already_tracks_the_final_payoff(self):
        a = self.a[120.0]
        b = self.b[120.0]
        self.assertEqual(a.n, 33)
        self.assertEqual(b.n, 30)
        self.assertAlmostEqual(a.r_squared, 0.906749625650, places=9)
        self.assertAlmostEqual(a.rmse, 97.040630704166, places=6)
        self.assertEqual(a.sign_agreement, 1.0)
        self.assertAlmostEqual(b.r_squared, 0.946729482773, places=9)
        self.assertAlmostEqual(b.rmse, 114.294424190640, places=6)
        self.assertAlmostEqual(b.sign_agreement, 0.9, places=12)

    def test_thirty_seconds_does_not(self):
        a = self.a[30.0]
        b = self.b[30.0]
        self.assertAlmostEqual(a.r_squared, 0.351082713457, places=9)
        self.assertAlmostEqual(a.rmse, 255.989994072668, places=6)
        self.assertAlmostEqual(b.r_squared, -0.020947884482, places=9)
        self.assertAlmostEqual(b.rmse, 500.360910380983, places=6)
        self.assertLess(b.r_squared, 0.0)

    def test_the_other_published_clocks(self):
        self.assertAlmostEqual(self.a[60.0].r_squared, 0.576210154527, places=9)
        self.assertAlmostEqual(self.a[60.0].rmse, 206.872894820964, places=6)
        self.assertAlmostEqual(self.b[60.0].r_squared, 0.782894671521, places=9)
        self.assertAlmostEqual(self.b[60.0].rmse, 230.736780485610, places=6)
        self.assertAlmostEqual(self.a[300.0].r_squared, 0.997748779822, places=9)
        self.assertAlmostEqual(self.a[300.0].rmse, 15.077776621741, places=6)
        self.assertAlmostEqual(self.b[300.0].r_squared, 0.999126538993, places=9)
        self.assertAlmostEqual(self.b[300.0].rmse, 14.635357931791, places=6)

    def test_the_cap_is_not_why_the_second_window_is_worse(self):
        raw_a = mark_launches(self.first, LinearTerms(cap=1e12))
        raw_b = mark_launches(self.second, LinearTerms(cap=1e12))
        self.assertEqual(raw_a.n_capped, 0)
        self.assertEqual(raw_b.n_capped, 0)
        self.assertAlmostEqual(raw_a.mean_payoff, -135.996582405226, places=9)
        self.assertAlmostEqual(raw_b.mean_payoff, -551.553606738964, places=9)
        clamped_gap = (
            mark_launches(self.second, self.terms).mean_payoff
            - mark_launches(self.first, self.terms).mean_payoff
        )
        self.assertLess(raw_b.mean_payoff - raw_a.mean_payoff, clamped_gap)

    def test_a_full_window_freeze_is_the_final_payoff(self):
        point = freeze_clock(self.first, self.terms, clocks=(900.0,))[0]
        self.assertAlmostEqual(point.r_squared, 1.0, places=12)
        self.assertAlmostEqual(point.rmse, 0.0, places=9)
        self.assertEqual(point.sign_agreement, 1.0)

    def test_the_canned_late_tape_is_not_decided_at_two_minutes(self):
        prints = path_from_trades(QUOTE0, TOKEN0, late_trades(), 900.0)
        samples = [(print_.t, print_.price) for print_ in prints]
        final = settle_linear(samples, self.terms).payoff_to_long
        frozen = settle_linear(
            [(t, price) for t, price in samples if t <= 120.0],
            self.terms,
        ).payoff_to_long
        # Nothing has printed. Flat carry pays the strike, not the tape.
        self.assertAlmostEqual(frozen, 33.64949456289831, places=8)
        self.assertGreater(final - frozen, 50.0)

    def test_the_days_are_already_apart_at_one_minute(self):
        gaps = {row.clock: row for row in window_gap(self.first, self.second, self.terms)}
        early = gaps[30.0]
        minute = gaps[60.0]
        done = gaps[None]
        self.assertAlmostEqual(early.mean_a, -25.020122121719815, places=9)
        self.assertAlmostEqual(early.mean_b, -122.69123117623016, places=9)
        self.assertAlmostEqual(early.t_stat, -1.185241296979766, places=9)
        self.assertGreater(abs(early.t_stat), 1.0)
        self.assertLess(abs(early.t_stat), 1.96)
        self.assertAlmostEqual(minute.mean_a, -64.60240137428828, places=9)
        self.assertAlmostEqual(minute.mean_b, -261.3493785186353, places=9)
        self.assertAlmostEqual(minute.gap, -196.74697714434706, places=9)
        self.assertAlmostEqual(minute.stderr, 97.5679417580879, places=9)
        self.assertAlmostEqual(minute.t_stat, -2.016512530644193, places=9)
        self.assertLess(minute.t_stat, -1.96)
        self.assertAlmostEqual(done.mean_a, -131.13230729971312, places=9)
        self.assertAlmostEqual(done.gap, -232.45967755027326, places=9)
        self.assertAlmostEqual(done.t_stat, -2.1572385182024143, places=9)
        # One minute already carries the expiry disagreement. Thirty seconds does not.
        self.assertLess(abs(minute.gap - done.gap), 40.0)
        self.assertGreater(abs(done.gap) - abs(early.gap), 100.0)

    def test_rank_cuts_are_the_14_oct_tertiles_and_are_not_refit(self):
        edges = tertile_edges(frozen_velocity(self.first, self.terms, 120.0))
        self.assertEqual(edges, (FROZEN_RANK_LOW, FROZEN_RANK_HIGH))
        self.assertAlmostEqual(FROZEN_RANK_LOW, -0.19015517148776662, places=12)
        self.assertAlmostEqual(FROZEN_RANK_HIGH, -0.005193783861860567, places=12)
        rank = frozen_rank(self.first, self.second, self.terms)
        self.assertEqual(rank.low_cut, FROZEN_RANK_LOW)
        self.assertEqual(rank.high_cut, FROZEN_RANK_HIGH)
        self.assertEqual(tuple(bin.n for bin in rank.reference), (11, 11, 11))
        self.assertEqual(tuple(bin.n for bin in rank.replication), (12, 8, 10))
        self.assertAlmostEqual(rank.reference[0].mean_payoff, -466.3589813743815, places=9)
        self.assertAlmostEqual(rank.reference[0].stderr, 99.73780149596381, places=9)
        self.assertAlmostEqual(rank.reference[1].mean_payoff, -69.00026675634457, places=9)
        self.assertAlmostEqual(rank.reference[2].mean_payoff, 141.96232623158673, places=9)
        self.assertAlmostEqual(rank.replication[0].mean_payoff, -942.8501900926755, places=9)
        self.assertAlmostEqual(rank.replication[0].stderr, 55.311408442086666, places=9)
        self.assertAlmostEqual(rank.replication[1].mean_payoff, -42.41236599739296, places=9)
        self.assertAlmostEqual(rank.replication[2].mean_payoff, 74.5741663591659, places=9)
        for bins in (rank.reference, rank.replication):
            self.assertLess(bins[0].mean_payoff, bins[1].mean_payoff)
            self.assertLess(bins[1].mean_payoff, bins[2].mean_payoff)
            self.assertLess(bins[0].mean_payoff, 0.0)
            self.assertGreater(bins[2].mean_payoff, 0.0)
        self.assertLess(
            rank.replication[0].mean_payoff,
            rank.reference[0].mean_payoff - 400.0,
        )

    def test_a_thirty_minute_window_is_not_this_comparison(self):
        with self.assertRaises(ValueError):
            window_gap(self.first, self.second, LinearTerms(window=1800.0))


if __name__ == "__main__":
    unittest.main()
