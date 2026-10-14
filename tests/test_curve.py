import unittest

from vdc.curve import QUOTE0, TOKEN0, BondingCurve, path_from_trades
from vdc.scenarios import SCENARIOS


class CurveTests(unittest.TestCase):
    def test_buy_raises_spot_and_keeps_k(self):
        curve = BondingCurve(QUOTE0, TOKEN0)
        k = curve.k
        spot = curve.spot
        tokens = curve.buy_quote(100.0)
        self.assertGreater(tokens, 0.0)
        self.assertGreater(curve.spot, spot)
        self.assertAlmostEqual(curve.k, k, places=9)

    def test_round_trip_restores_reserves(self):
        # No fee: selling the tokens just bought returns the quote exactly.
        curve = BondingCurve(QUOTE0, TOKEN0)
        tokens = curve.buy_quote(100.0)
        quote_back = curve.sell_tokens(tokens)
        self.assertAlmostEqual(quote_back, 100.0, places=9)
        self.assertAlmostEqual(curve.quote, QUOTE0, places=9)
        self.assertAlmostEqual(curve.token, TOKEN0, places=6)

    def test_same_quote_in_same_terminal_spot(self):
        window = 900.0
        ends = []
        for name in ("sniper", "grind", "late"):
            prints = path_from_trades(QUOTE0, TOKEN0, SCENARIOS[name](), window)
            ends.append(prints[-1].price)
        self.assertAlmostEqual(ends[0], ends[1], places=12)
        self.assertAlmostEqual(ends[1], ends[2], places=12)
        self.assertGreater(ends[0], path_from_trades(QUOTE0, TOKEN0, [], window)[0].price)

    def test_trade_outside_window_rejected(self):
        with self.assertRaises(ValueError):
            path_from_trades(QUOTE0, TOKEN0, [("buy", 901.0, 10.0)], 900.0)


if __name__ == "__main__":
    unittest.main()
