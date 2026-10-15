"""The inception gap is composition. Same frozen velocity, same payoff."""

import math
import unittest
from pathlib import Path

from vdc.contract import LinearTerms
from vdc.fit import load_launches
from vdc.freeze import COMPOSITION_CLOCK, COMPOSITION_EDGES, composition

ROOT = Path(__file__).resolve().parents[1]


class CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.windows = [
            load_launches(str(ROOT / "data" / "launches.json")),
            load_launches(str(ROOT / "data" / "launches_b.json")),
            load_launches(str(ROOT / "data" / "launches_c.json")),
        ]
        cls.terms = LinearTerms()
        cls.result = composition(cls.windows, cls.terms)

    def test_the_grid_is_declared_and_the_spec_does_not_move(self):
        self.assertEqual(self.result.clock, COMPOSITION_CLOCK)
        self.assertEqual(self.result.clock, 120.0)
        self.assertEqual(self.result.edges, COMPOSITION_EDGES)
        self.assertEqual(self.terms.half_life, 120.0)
        self.assertAlmostEqual(self.terms.strike_per_minute, -0.03364949456289831, places=12)
        self.assertEqual(self.terms.notional, 1000.0)
        self.assertEqual(self.terms.cap, 1000.0)

    def test_only_the_later_windows_had_already_hit_the_cap(self):
        crash = self.result.bins[0]
        self.assertIsNone(crash.low)
        self.assertEqual(crash.high, -1.0)
        self.assertEqual(crash.cells[0].n, 0)
        self.assertIsNone(crash.cells[0].mean_payoff)
        self.assertEqual(tuple(cell.n for cell in crash.cells), (0, 8, 4))
        self.assertEqual(crash.cells[1].mean_payoff, -1000.0)
        self.assertEqual(crash.cells[2].mean_payoff, -1000.0)
        self.assertEqual(crash.cells[1].stderr, 0.0)
        self.assertEqual(crash.cells[2].stderr, 0.0)

    def test_the_common_grid_is_locked(self):
        expected = (
            ((4, -828.3124008925163), (3, -993.1631398747867), (3, -823.9746967291862)),
            ((7, -259.52845593544737), (1, -334.71286148774647), (5, -445.05872389845024)),
            ((11, -69.00026675634457), (8, -42.41236599739296), (10, -15.997306309194093)),
            ((4, 71.82200372453465), (6, 9.782896335760563), (4, 33.233504355288055)),
            ((7, 182.04251052133083), (4, 171.7610713942739), (4, 83.22926337845594)),
        )
        for bin_, rows in zip(self.result.bins[1:], expected):
            for cell, (n, mean) in zip(bin_.cells, rows):
                self.assertEqual(cell.n, n)
                self.assertAlmostEqual(cell.mean_payoff, mean, places=9)
        # One tape. Listed, not a result.
        self.assertIsNone(self.result.bins[2].cells[1].stderr)
        mild = self.result.bins[1]
        diff = mild.cells[2].mean_payoff - mild.cells[0].mean_payoff
        se = math.sqrt(mild.cells[0].stderr**2 + mild.cells[2].stderr**2)
        self.assertLess(abs(diff / se), 0.1)
        top = self.result.bins[5]
        diff = top.cells[2].mean_payoff - top.cells[0].mean_payoff
        se = math.sqrt(top.cells[0].stderr**2 + top.cells[2].stderr**2)
        self.assertAlmostEqual(diff / se, -2.124423822041957, places=9)

    def test_overlap_means_agree_and_the_slope_is_one(self):
        self.assertAlmostEqual(self.result.overlap_low, -0.9669381678786427, places=12)
        self.assertAlmostEqual(self.result.overlap_high, 0.2462935504738795, places=12)
        overlap = (
            (31, -159.93098681384475),
            (21, -156.82845294778488),
            (26, -168.89768083987596),
        )
        for cell, (n, mean) in zip(self.result.overlap, overlap):
            self.assertEqual(cell.n, n)
            self.assertAlmostEqual(cell.mean_payoff, mean, places=9)
        spread = max(cell.mean_payoff for cell in self.result.overlap) - min(
            cell.mean_payoff for cell in self.result.overlap
        )
        self.assertLess(spread, 15.0)
        maps = (
            (1.0943871178834552, -20.47686083597506, 88.44584923791913, -30.020511797454542, 16.31300562327604),
            (1.0333073784220694, -34.57819700740714, 103.81748157762782, -45.18354732870817, 19.495059013153988),
            (1.0161156176989872, -44.34564042615739, 127.32812078027746, -48.07854571775128, 23.673146229527),
        )
        for row, expected in zip(self.result.windows, maps):
            slope, intercept, rmse, residual, stderr = expected
            self.assertAlmostEqual(row.slope, slope, places=9)
            self.assertAlmostEqual(row.intercept, intercept, places=9)
            self.assertAlmostEqual(row.rmse, rmse, places=9)
            self.assertAlmostEqual(row.residual_mean, residual, places=9)
            self.assertAlmostEqual(row.residual_stderr, stderr, places=9)
            self.assertGreater(row.slope, 1.0)
            self.assertLess(row.slope, 1.10)
        for left in range(3):
            for right in range(left + 1, 3):
                a = self.result.windows[left]
                b = self.result.windows[right]
                se = math.sqrt(a.residual_stderr**2 + b.residual_stderr**2)
                self.assertLess(abs(b.residual_mean - a.residual_mean) / se, 1.0)

    def test_a_single_window_or_the_wrong_length_is_refused(self):
        with self.assertRaises(ValueError):
            composition([self.windows[0]], self.terms)
        with self.assertRaises(ValueError):
            composition(self.windows, LinearTerms(window=1800.0))
