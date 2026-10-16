"""The average leftover is a mix. Two states are finished. One is not."""

import math
import unittest
from pathlib import Path

from vdc.contract import LinearTerms
from vdc.fit import load_launches
from vdc.freeze import (
    COMPOSITION_EDGES,
    RESIDUAL_SPLIT,
    _ols,
    _pairs,
    residual_states,
)

ROOT = Path(__file__).resolve().parents[1]


def _rmse(errors: list[float]) -> float:
    return math.sqrt(sum(error * error for error in errors) / len(errors))


class ResidualStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.windows = [
            load_launches(str(ROOT / "data" / "launches.json")),
            load_launches(str(ROOT / "data" / "launches_b.json")),
            load_launches(str(ROOT / "data" / "launches_c.json")),
        ]
        cls.terms = LinearTerms()
        cls.result = residual_states(cls.windows, cls.terms)

    def test_the_split_is_the_declared_edge_and_the_spec_does_not_move(self):
        self.assertEqual(self.result.clock, 120.0)
        self.assertEqual(self.result.split, RESIDUAL_SPLIT)
        self.assertEqual(self.result.split, -0.19)
        self.assertEqual(self.result.split, COMPOSITION_EDGES[2])
        self.assertEqual(tuple(state.name for state in self.result.states), ("capped", "left", "middle", "above"))
        self.assertEqual(self.terms.half_life, 120.0)
        self.assertAlmostEqual(self.terms.strike_per_minute, -0.03364949456289831, places=12)

    def test_the_cap_and_the_middle_are_finished(self):
        capped, left, middle, above = self.result.states
        self.assertEqual(tuple(cell.n for cell in capped.cells), (0, 8, 4))
        self.assertIsNone(capped.cells[0].mean_residual)
        self.assertEqual(capped.cells[1].mean_residual, 0.0)
        self.assertEqual(capped.cells[2].mean_residual, 0.0)
        self.assertEqual(tuple(cell.n for cell in middle.cells), (11, 10, 11))
        self.assertAlmostEqual(middle.cells[0].mean_residual, -13.825214878275444, places=9)
        self.assertAlmostEqual(middle.cells[0].stderr, 6.548299422278348, places=9)
        self.assertAlmostEqual(middle.cells[1].mean_residual, 2.021775437267769, places=9)
        self.assertAlmostEqual(middle.cells[1].stderr, 1.9435195409940051, places=9)
        self.assertAlmostEqual(middle.cells[2].mean_residual, -4.704449398112955, places=9)
        self.assertAlmostEqual(middle.cells[2].stderr, 2.0002859684564784, places=9)
        for cell in middle.cells:
            self.assertLess(abs(cell.mean_residual), 15.0)

    def test_the_uncapped_crash_has_no_level_and_the_upside_is_not_a_rule(self):
        left = self.result.states[1]
        above = self.result.states[3]
        self.assertEqual(tuple(cell.n for cell in left.cells), (11, 4, 8))
        self.assertAlmostEqual(left.cells[0].mean_residual, -73.03483110923202, places=9)
        self.assertAlmostEqual(left.cells[0].stderr, 46.22785945576842, places=9)
        self.assertAlmostEqual(left.cells[1].mean_residual, -262.6419029673475, places=9)
        self.assertAlmostEqual(left.cells[1].stderr, 87.77850077149247, places=9)
        self.assertAlmostEqual(left.cells[2].mean_residual, -129.9381152282482, places=9)
        self.assertAlmostEqual(left.cells[2].stderr, 82.9693938661225, places=9)
        for cell in left.cells:
            self.assertLess(cell.mean_residual, 0.0)
        spread = max(cell.mean_residual for cell in left.cells) - min(
            cell.mean_residual for cell in left.cells
        )
        self.assertGreater(spread, 150.0)
        self.assertEqual(tuple(cell.n for cell in above.cells), (11, 8, 7))
        self.assertAlmostEqual(above.cells[0].mean_residual, -3.2014894048561726, places=9)
        self.assertAlmostEqual(above.cells[0].stderr, 9.571975838519108, places=9)
        self.assertAlmostEqual(above.cells[1].mean_residual, -40.64457029556662, places=9)
        self.assertAlmostEqual(above.cells[1].stderr, 13.306768034089387, places=9)
        self.assertAlmostEqual(above.cells[2].mean_residual, -50.157500903901465, places=9)
        self.assertAlmostEqual(above.cells[2].stderr, 20.72787391392867, places=9)
        self.assertGreater(above.cells[0].mean_residual, -10.0)
        self.assertLess(above.cells[1].mean_residual, -30.0)
        self.assertLess(above.cells[2].mean_residual, -30.0)

    def test_a_slope_fit_on_the_first_window_makes_the_later_ones_worse(self):
        pairs = [_pairs(window, self.terms, 120.0) for window in self.windows]
        first = pairs[0]
        slope, intercept, _ = _ols(
            [velocity for velocity, _, _ in first],
            [final - frozen for _, frozen, final in first],
        )
        haircut = sum(final - frozen for _, frozen, final in first) / len(first)

        def flat(rows):
            return _rmse([final - frozen for _, frozen, final in rows])

        def line(rows):
            return _rmse(
                [final - (frozen + intercept + slope * velocity) for velocity, frozen, final in rows]
            )

        def shifted(rows):
            return _rmse([final - (frozen + haircut) for _, frozen, final in rows])

        for rows in pairs[1:]:
            self.assertGreater(line(rows), flat(rows))
        for rows in pairs:
            self.assertLess(flat(rows) - shifted(rows), 15.0)
            self.assertGreater(flat(rows) - shifted(rows), 0.0)

    def test_a_single_window_or_the_wrong_length_is_refused(self):
        with self.assertRaises(ValueError):
            residual_states([self.windows[0]], self.terms)
        with self.assertRaises(ValueError):
            residual_states(self.windows, LinearTerms(window=1800.0))
