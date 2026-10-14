"""Constant-product bonding curve, desk units.

Spot = quote / token, k = quote * token. Buying with quote raises spot.
The same quote in, in any order, ends at the same spot — which is why three
launch tapes can share a terminal price and still have different velocities.
"""

from __future__ import annotations

from dataclasses import dataclass

QUOTE0 = 1000.0
TOKEN0 = 1_000_000.0


class BondingCurve:
    def __init__(self, quote_reserve: float, token_reserve: float) -> None:
        if quote_reserve <= 0 or token_reserve <= 0:
            raise ValueError("reserves must be positive")
        self.quote = float(quote_reserve)
        self.token = float(token_reserve)

    @property
    def spot(self) -> float:
        return self.quote / self.token

    @property
    def k(self) -> float:
        return self.quote * self.token

    def buy_quote(self, dq: float) -> float:
        """Spend `dq` quote. Returns tokens out."""
        if dq <= 0:
            raise ValueError("buy size must be positive")
        k = self.k
        self.quote += dq
        new_token = k / self.quote
        out = self.token - new_token
        self.token = new_token
        return out

    def sell_tokens(self, amount: float) -> float:
        """Return `amount` tokens to the curve. Returns quote out."""
        if amount <= 0:
            raise ValueError("sell size must be positive")
        if amount >= self.token:
            raise ValueError("sell would exhaust the token reserve")
        k = self.k
        self.token += amount
        new_quote = k / self.token
        out = self.quote - new_quote
        self.quote = new_quote
        return out


@dataclass(frozen=True)
class Print:
    t: float
    price: float
    quote: float
    token: float
    kind: str
    size: float


def path_from_trades(
    quote0: float,
    token0: float,
    trades: tuple[tuple[str, float, float], ...] | list[tuple[str, float, float]],
    window: float,
) -> list[Print]:
    """Build a print tape. Buy size is quote in. Sell size is quote to lift, capped."""
    if window <= 0:
        raise ValueError("window must be positive")
    curve = BondingCurve(quote0, token0)
    prints = [Print(0.0, curve.spot, curve.quote, curve.token, "open", 0.0)]
    for kind, t, size in sorted(trades, key=lambda row: row[1]):
        if t < 0 or t > window:
            raise ValueError(f"trade time {t} outside [0, {window}]")
        if kind == "buy":
            curve.buy_quote(size)
            prints.append(Print(float(t), curve.spot, curve.quote, curve.token, "buy", float(size)))
        elif kind == "sell":
            tokens = min(curve.token * 0.25, size / curve.spot)
            if tokens <= 0:
                continue
            quote_out = curve.sell_tokens(tokens)
            prints.append(Print(float(t), curve.spot, curve.quote, curve.token, "sell", quote_out))
        else:
            raise ValueError(f"unknown trade kind {kind}")
    return prints
