"""Choose the half-life by time-reversal, then set the strike at the 60th percentile.

Partial correlation against a clock-time earliness score does not identify the
kernel on these tapes: almost every launch is already front-loaded, so the
score has no contrast and the partial flips sign. Time reversal keeps the
same log-return and the same interval lengths, and swaps the order of the
returns. A flat kernel is invariant to that. A decay kernel is not. The
half-life with the largest mean gap relative to its own dispersion is the
one that actually prices timing.

The strike is the 60th percentile of velocity under that kernel, so about
40% of this sample finishes in the money for the long.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from vdc.velocity import decay_weighted_velocity, prepare_path

WINDOW = 900.0
HALF_LIVES = (120.0, 300.0, 600.0, math.inf)
STRIKE_PERCENTILE = 0.60


def time_reversed(samples: list[tuple[float, float]], window: float) -> list[tuple[float, float]]:
    path = prepare_path(samples, window)
    dts: list[float] = []
    returns: list[float] = []
    for i in range(1, len(path)):
        t0, p0 = path[i - 1]
        t1, p1 = path[i]
        dts.append(t1 - t0)
        returns.append(math.log(p1 / p0))
    price = path[0][1]
    cursor = 0.0
    out = [(0.0, price)]
    for dt, r in zip(dts, reversed(returns)):
        cursor += dt
        price *= math.exp(r)
        out.append((cursor, price))
    return out


def _gap(samples: list[tuple[float, float]], window: float, half_life: float) -> float:
    forward = decay_weighted_velocity(samples, window, half_life).per_minute
    backward = decay_weighted_velocity(time_reversed(samples, window), window, half_life).per_minute
    return forward - backward


def _percentile(xs: list[float], p: float) -> float:
    ordered = sorted(xs)
    k = (len(ordered) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - k) + ordered[hi] * (k - lo)


@dataclass(frozen=True)
class KernelScore:
    half_life: float
    mean_gap: float
    sd_gap: float
    t_stat: float


@dataclass(frozen=True)
class Fit:
    half_life: float
    strike_per_minute: float
    n: int
    hit_rate: float
    kernels: tuple[KernelScore, ...]


def _summarize(gaps: list[float], half_life: float) -> KernelScore:
    n = len(gaps)
    mean = sum(gaps) / n
    var = sum((g - mean) ** 2 for g in gaps) / (n - 1)
    sd = math.sqrt(var)
    t_stat = 0.0 if sd < 1e-12 else mean / (sd / math.sqrt(n))
    return KernelScore(half_life, mean, sd, t_stat)


def fit_launches(launches: list[dict], window: float = WINDOW) -> Fit:
    if len(launches) < 8:
        raise ValueError(f"need at least 8 tapes, got {len(launches)}")
    gaps: dict[float, list[float]] = {half_life: [] for half_life in HALF_LIVES}
    velocities: dict[float, list[float]] = {half_life: [] for half_life in HALF_LIVES}
    for launch in launches:
        samples = [(float(t), float(price)) for t, price in launch["samples"]]
        for half_life in HALF_LIVES:
            velocities[half_life].append(
                decay_weighted_velocity(samples, window, half_life).per_minute
            )
            gaps[half_life].append(_gap(samples, window, half_life))
    kernels = tuple(_summarize(gaps[half_life], half_life) for half_life in HALF_LIVES)
    decay = [kernel for kernel in kernels if not math.isinf(kernel.half_life)]
    chosen = max(decay, key=lambda kernel: abs(kernel.t_stat)).half_life
    sample = velocities[chosen]
    strike = _percentile(sample, STRIKE_PERCENTILE)
    hit = sum(1 for value in sample if value >= strike) / len(sample)
    return Fit(chosen, strike, len(launches), hit, kernels)


def load_launches(path: str) -> list[dict]:
    import json

    with open(path) as handle:
        return json.load(handle)["launches"]
