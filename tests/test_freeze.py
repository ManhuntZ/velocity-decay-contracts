"""Flat-carry at a clock, against the finished tape. Not a new spec."""

import unittest
from pathlib import Path

from vdc.contract import LinearTerms, settle_linear
from vdc.curve import QUOTE0, TOKEN0, path_from_trades
from vdc.fit import load_launches
from vdc.freeze import freeze_clock
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


if __name__ == "__main__":
    unittest.main()
