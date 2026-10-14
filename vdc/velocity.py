"""Decay-weighted log-price velocity.

The contract does not use an endpoint slope. Instantaneous log-velocity is
averaged over a fixed window with an exponential kernel, so a print early in
the launch is worth more than the same print near expiry.

    v(t) = d/dt ln P(t)
    w(t) = exp(-λ t),  λ = ln(2) / half_life
    V    = ∫ v(t) w(t) dt  /  ∫ w(t) dt

Between prints, log-price is treated as linear (constant v). Time after the
last print and before expiry is flat: velocity zero, which dilutes V. Prints
outside [0, window] are ignored. An anchor print at t = 0 is required.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Velocity:
    per_second: float
    per_minute: float
    log_return: float
    price_start: float
    price_end: float
    samples: int


def decay_weight_integral(a: float, b: float, lam: float) -> float:
    """∫_a^b exp(-λ t) dt. λ = 0 is the uniform kernel."""
    if b < a:
        raise ValueError("inverted interval")
    dt = b - a
    if dt == 0.0:
        return 0.0
    if lam == 0.0:
        return dt
    # e^{-λa} * (1 - e^{-λ dt}) / λ, stable for small λ·dt
    return math.exp(-lam * a) * (-math.expm1(-lam * dt)) / lam


def prepare_path(
    samples: list[tuple[float, float]],
    window: float,
) -> list[tuple[float, float]]:
    """Clip to the window, collapse duplicate times, flat-carry to expiry."""
    if window <= 0:
        raise ValueError("window must be positive")
    kept: list[tuple[float, float]] = []
    for t, price in samples:
        if not math.isfinite(t) or not math.isfinite(price):
            raise ValueError("time and price must be finite")
        if price <= 0:
            raise ValueError("price must be positive")
        if t < 0 or t > window:
            continue
        kept.append((float(t), float(price)))
    if not kept:
        raise ValueError("no samples inside the window")
    kept.sort(key=lambda row: row[0])
    collapsed: list[tuple[float, float]] = []
    for t, price in kept:
        if collapsed and collapsed[-1][0] == t:
            collapsed[-1] = (t, price)
        else:
            collapsed.append((t, price))
    if collapsed[0][0] != 0.0:
        raise ValueError("anchor print at t=0 is required")
    if collapsed[-1][0] < window:
        collapsed.append((window, collapsed[-1][1]))
    return collapsed


def _lambda(half_life: float) -> float:
    if half_life <= 0:
        raise ValueError("half_life must be positive (math.inf = uniform)")
    if math.isinf(half_life):
        return 0.0
    return math.log(2.0) / half_life


def decay_weighted_velocity(
    samples: list[tuple[float, float]],
    window: float,
    half_life: float,
) -> Velocity:
    path = prepare_path(samples, window)
    return _velocity(path, window, half_life)


def _velocity(path: list[tuple[float, float]], window: float, half_life: float) -> Velocity:
    lam = _lambda(half_life)
    denom = decay_weight_integral(0.0, window, lam)
    if denom <= 0:
        raise ValueError("kernel weight over the window is zero")
    numer = 0.0
    log_return = 0.0
    for i in range(1, len(path)):
        t0, p0 = path[i - 1]
        t1, p1 = path[i]
        dt = t1 - t0
        if dt <= 0:
            continue
        r = math.log(p1 / p0)
        log_return += r
        numer += (r / dt) * decay_weight_integral(t0, t1, lam)
    per_second = numer / denom
    return Velocity(
        per_second=per_second,
        per_minute=per_second * 60.0,
        log_return=log_return,
        price_start=path[0][1],
        price_end=path[-1][1],
        samples=len(path),
    )


def log_slope_per_minute(samples: list[tuple[float, float]], window: float) -> float:
    """Uniform-kernel log velocity. Equals decay-weighted V at infinite half-life."""
    path = prepare_path(samples, window)
    return math.log(path[-1][1] / path[0][1]) * 60.0 / window


def arithmetic_slope_per_minute(samples: list[tuple[float, float]], window: float) -> float:
    """Endpoint arithmetic slope used by the first sketch. Not the contract."""
    path = prepare_path(samples, window)
    return (path[-1][1] / path[0][1] - 1.0) * 60.0 / window
