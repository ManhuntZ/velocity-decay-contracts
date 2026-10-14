"""Fully collateralized settlement.

Linear (the desk instrument)
    payoff to the long = clamp(notional * (V - K), -cap, cap)
    Each side posts `cap`. The clamp is what makes that collateral enough.

Digital
    Long pays `premium` at inception. Short posts `payout - premium`.
    If V >= K the long is paid `payout` (profit payout - premium).
    Otherwise the short keeps the premium. Premium must sit inside (0, payout).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from vdc.velocity import (
    arithmetic_slope_per_minute,
    decay_weighted_velocity,
    log_slope_per_minute,
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass(frozen=True)
class LinearTerms:
    window: float = 900.0
    # data/launches.json, 14 Oct 2026, n=33. Time reversal picks 120s.
    # Strike is the 60th percentile of V under that kernel.
    half_life: float = 120.0
    strike_per_minute: float = -0.03364949456289831
    notional: float = 1000.0
    cap: float = 1000.0

    def __post_init__(self) -> None:
        if self.window <= 0:
            raise ValueError("window must be positive")
        if math.isnan(self.half_life) or (not math.isinf(self.half_life) and self.half_life <= 0):
            raise ValueError("half_life must be positive or +inf")
        if self.notional < 0:
            raise ValueError("notional must be >= 0")
        if self.cap <= 0:
            raise ValueError("cap must be positive")
        if not math.isfinite(self.strike_per_minute):
            raise ValueError("strike must be finite")


@dataclass(frozen=True)
class Settlement:
    velocity_per_minute: float
    log_slope_per_minute: float
    arithmetic_slope_per_minute: float
    log_return: float
    price_start: float
    price_end: float
    payoff_to_long: float
    capped: bool


def settle_linear(
    samples: list[tuple[float, float]],
    terms: LinearTerms,
) -> Settlement:
    velocity = decay_weighted_velocity(samples, terms.window, terms.half_life)
    raw = terms.notional * (velocity.per_minute - terms.strike_per_minute)
    payoff = _clamp(raw, -terms.cap, terms.cap)
    return Settlement(
        velocity_per_minute=velocity.per_minute,
        log_slope_per_minute=log_slope_per_minute(samples, terms.window),
        arithmetic_slope_per_minute=arithmetic_slope_per_minute(samples, terms.window),
        log_return=velocity.log_return,
        price_start=velocity.price_start,
        price_end=velocity.price_end,
        payoff_to_long=payoff,
        capped=payoff != raw,
    )


@dataclass(frozen=True)
class DigitalTerms:
    window: float = 900.0
    half_life: float = 300.0
    strike_per_minute: float = 0.05
    payout: float = 1.0
    premium: float = 0.4

    def __post_init__(self) -> None:
        if self.window <= 0:
            raise ValueError("window must be positive")
        if self.half_life <= 0 or math.isnan(self.half_life):
            raise ValueError("half_life must be positive or +inf")
        if self.payout <= 0:
            raise ValueError("payout must be positive")
        if not (0.0 < self.premium < self.payout):
            raise ValueError("premium must sit strictly inside the payout")


@dataclass(frozen=True)
class DigitalSettlement:
    velocity_per_minute: float
    hit: bool
    long_pnl: float
    short_pnl: float


def settle_digital(
    samples: list[tuple[float, float]],
    terms: DigitalTerms,
) -> DigitalSettlement:
    velocity = decay_weighted_velocity(samples, terms.window, terms.half_life)
    hit = velocity.per_minute >= terms.strike_per_minute
    long_pnl = (terms.payout - terms.premium) if hit else -terms.premium
    return DigitalSettlement(
        velocity_per_minute=velocity.per_minute,
        hit=hit,
        long_pnl=long_pnl,
        short_pnl=-long_pnl,
    )
