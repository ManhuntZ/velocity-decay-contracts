"""Front-loaded Poisson simulator. Not the pricing measure.

Buys arrive as an inhomogeneous Poisson process with decaying intensity.
Sells start after a delay, also decaying. Sizes are lognormal. Kept so the
path generator stays reproducible. The inception mark is the mean payoff on
the shipped tapes, not a draw from this flow.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from vdc.contract import LinearTerms, settle_linear
from vdc.curve import BondingCurve, Print


@dataclass(frozen=True)
class Flow:
    window: float
    buy_peak: float
    buy_tau: float
    sell_peak: float
    sell_tau: float
    sell_start: float
    buy_median: float
    buy_sigma: float
    sell_median: float
    sell_sigma: float

    def buy_rate(self, t: float) -> float:
        return self.buy_peak * math.exp(-t / self.buy_tau)

    def sell_rate(self, t: float) -> float:
        if t < self.sell_start:
            return 0.0
        return self.sell_peak * math.exp(-(t - self.sell_start) / self.sell_tau)


# Expected buys ≈ buy_peak * buy_tau ≈ 31.5 over 900s. Front-loaded.
FRONT_LOADED = Flow(
    window=900.0,
    buy_peak=0.35,
    buy_tau=90.0,
    sell_peak=0.08,
    sell_tau=180.0,
    sell_start=120.0,
    buy_median=40.0,
    buy_sigma=0.55,
    sell_median=25.0,
    sell_sigma=0.45,
)


def _lognormal(rng: random.Random, median: float, sigma: float) -> float:
    return rng.lognormvariate(math.log(median), sigma)


def _thin(rng: random.Random, t: float, horizon: float, rate_fn, rate_max: float) -> float | None:
    if rate_max <= 0:
        return None
    while True:
        t += rng.expovariate(rate_max)
        if t >= horizon:
            return None
        rate = rate_fn(t)
        if rate > rate_max * (1.0 + 1e-9):
            raise RuntimeError("intensity exceeds the thinning bound")
        if rate > 0.0 and rng.random() < rate / rate_max:
            return t


def simulate_flow(
    quote0: float,
    token0: float,
    flow: Flow,
    rng: random.Random,
) -> list[Print]:
    curve = BondingCurve(quote0, token0)
    prints = [Print(0.0, curve.spot, curve.quote, curve.token, "open", 0.0)]
    next_buy = _thin(rng, 0.0, flow.window, flow.buy_rate, flow.buy_peak)
    next_sell = _thin(rng, 0.0, flow.window, flow.sell_rate, flow.sell_peak)
    steps = 0
    while steps < 100_000:
        steps += 1
        pending: list[tuple[str, float]] = []
        if next_buy is not None:
            pending.append(("buy", next_buy))
        if next_sell is not None:
            pending.append(("sell", next_sell))
        if not pending:
            break
        kind, t = min(pending, key=lambda row: row[1])
        if kind == "buy":
            size = _lognormal(rng, flow.buy_median, flow.buy_sigma)
            curve.buy_quote(size)
            prints.append(Print(t, curve.spot, curve.quote, curve.token, "buy", size))
            next_buy = _thin(rng, t, flow.window, flow.buy_rate, flow.buy_peak)
        else:
            size = _lognormal(rng, flow.sell_median, flow.sell_sigma)
            tokens = min(curve.token * 0.25, size / curve.spot)
            if tokens > 0.0:
                quote_out = curve.sell_tokens(tokens)
                prints.append(Print(t, curve.spot, curve.quote, curve.token, "sell", quote_out))
            next_sell = _thin(rng, t, flow.window, flow.sell_rate, flow.sell_peak)
    else:
        raise RuntimeError("flow simulation did not terminate")
    return prints


@dataclass(frozen=True)
class MonteCarlo:
    fair_to_long: float
    stderr: float
    n: int
    mean_velocity: float


def monte_carlo_linear(
    quote0: float,
    token0: float,
    flow: Flow,
    terms: LinearTerms,
    n: int = 200,
    seed: int = 7,
) -> MonteCarlo:
    if n < 2:
        raise ValueError("n must be at least 2")
    if terms.window != flow.window:
        raise ValueError("terms.window and flow.window must match")
    rng = random.Random(seed)
    pays: list[float] = []
    vels: list[float] = []
    for _ in range(n):
        prints = simulate_flow(quote0, token0, flow, rng)
        samples = [(p.t, p.price) for p in prints]
        settled = settle_linear(samples, terms)
        pays.append(settled.payoff_to_long)
        vels.append(settled.velocity_per_minute)
    mean = sum(pays) / n
    var = sum((p - mean) ** 2 for p in pays) / (n - 1)
    return MonteCarlo(
        fair_to_long=mean,
        stderr=math.sqrt(var / n),
        n=n,
        mean_velocity=sum(vels) / n,
    )
