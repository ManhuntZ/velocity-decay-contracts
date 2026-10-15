"""If the tape froze.

Drop every print after a clock, then settle the remainder under the same
terms. Flat carry to expiry is already what settlement does after the last
print. The result is that counterfactual, not E[payoff | path so far].
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from vdc.contract import LinearTerms, settle_linear

# Clocks reported against the 15-minute window. 120s is one spec half-life.
FREEZE_CLOCKS = (30.0, 60.0, 120.0, 300.0)


@dataclass(frozen=True)
class FreezePoint:
    clock: float
    r_squared: float
    rmse: float
    sign_agreement: float
    n: int


def _sign(value: float) -> int:
    if value > 0.0:
        return 1
    if value < 0.0:
        return -1
    return 0


def freeze_clock(
    launches: list[dict],
    terms: LinearTerms,
    clocks: tuple[float, ...] = FREEZE_CLOCKS,
) -> list[FreezePoint]:
    """R², RMSE, and sign agreement of flat-carry payoff against the final payoff.

    R² is 1 − SS_res / SS_tot, with SS_tot taken on the final payoff. RMSE is
    the root mean squared error, divided by n. Sign agreement is the share of
    tapes whose payoff is positive, negative, or zero on both settlements.
    """
    if terms.window != 900.0:
        raise ValueError(f"freeze clock is a 900s window, got {terms.window}")
    if len(launches) < 8:
        raise ValueError(f"need at least 8 tapes, got {len(launches)}")
    if not clocks:
        raise ValueError("need at least one clock")

    paths: list[list[tuple[float, float]]] = []
    final: list[float] = []
    for launch in launches:
        samples = [(float(t), float(price)) for t, price in launch["samples"]]
        paths.append(samples)
        final.append(settle_linear(samples, terms).payoff_to_long)

    n = len(final)
    mean = sum(final) / n
    ss_tot = sum((payoff - mean) ** 2 for payoff in final)
    if ss_tot == 0.0:
        raise ValueError("final payoffs have no variance")

    points: list[FreezePoint] = []
    for clock in clocks:
        if not math.isfinite(clock) or clock <= 0.0 or clock > terms.window:
            raise ValueError(f"clock must sit in (0, {terms.window:.0f}]")
        frozen: list[float] = []
        for samples in paths:
            cut = [(t, price) for t, price in samples if t <= clock]
            frozen.append(settle_linear(cut, terms).payoff_to_long)
        ss_res = sum((y - yhat) ** 2 for y, yhat in zip(final, frozen))
        agree = sum(_sign(y) == _sign(yhat) for y, yhat in zip(final, frozen))
        points.append(
            FreezePoint(
                clock=clock,
                r_squared=1.0 - ss_res / ss_tot,
                rmse=math.sqrt(ss_res / n),
                sign_agreement=agree / n,
                n=n,
            )
        )
    return points


# Frozen log-velocity at one half-life on data/launches.json, 14 Oct 2026, n=33.
# Thirds of 11: sorted(V)[10] and sorted(V)[21]. Later windows are scored on
# these cuts. Do not refit them on a new sample.
FROZEN_RANK_CLOCK = 120.0
FROZEN_RANK_LOW = -0.19015517148776662
FROZEN_RANK_HIGH = -0.005193783861860567


@dataclass(frozen=True)
class WindowGap:
    """clock is None for the finished tape. gap is second minus first."""

    clock: float | None
    mean_a: float
    mean_b: float
    gap: float
    stderr: float
    t_stat: float


@dataclass(frozen=True)
class RankBin:
    n: int
    mean_payoff: float
    stderr: float


@dataclass(frozen=True)
class FrozenRank:
    clock: float
    low_cut: float
    high_cut: float
    reference: tuple[RankBin, RankBin, RankBin]
    replication: tuple[RankBin, RankBin, RankBin]


def _payoffs(
    launches: list[dict],
    terms: LinearTerms,
    clock: float | None,
) -> list[float]:
    out: list[float] = []
    for launch in launches:
        samples = [(float(t), float(price)) for t, price in launch["samples"]]
        if clock is not None:
            samples = [(t, price) for t, price in samples if t <= clock]
        out.append(settle_linear(samples, terms).payoff_to_long)
    return out


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _stderr_of_mean(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        raise ValueError(f"need at least 2 tapes, got {n}")
    center = _mean(values)
    var = sum((value - center) ** 2 for value in values) / (n - 1)
    return math.sqrt(var / n)


def window_gap(
    first: list[dict],
    second: list[dict],
    terms: LinearTerms,
    clocks: tuple[float, ...] = (30.0, 60.0, 120.0),
) -> list[WindowGap]:
    """Flat-carry mean payoff on each window, then the finished tape.

    The gap is the second window minus the first. The standard error is the
    standard error of that difference of means. This is not a pooled price.
    """
    if terms.window != 900.0:
        raise ValueError(f"window gap is a 900s window, got {terms.window}")
    if len(first) < 8 or len(second) < 8:
        raise ValueError("each window needs at least 8 tapes")
    rows: list[WindowGap] = []
    for clock in (*clocks, None):
        if clock is not None and (
            not math.isfinite(clock) or clock <= 0.0 or clock > terms.window
        ):
            raise ValueError(f"clock must sit in (0, {terms.window:.0f}]")
        left = _payoffs(first, terms, clock)
        right = _payoffs(second, terms, clock)
        gap = _mean(right) - _mean(left)
        stderr = math.sqrt(_stderr_of_mean(left) ** 2 + _stderr_of_mean(right) ** 2)
        rows.append(
            WindowGap(
                clock=clock,
                mean_a=_mean(left),
                mean_b=_mean(right),
                gap=gap,
                stderr=stderr,
                t_stat=gap / stderr,
            )
        )
    return rows


def frozen_velocity(
    launches: list[dict],
    terms: LinearTerms,
    clock: float,
) -> list[float]:
    if terms.window != 900.0:
        raise ValueError(f"frozen velocity is a 900s window, got {terms.window}")
    if not math.isfinite(clock) or clock <= 0.0 or clock > terms.window:
        raise ValueError(f"clock must sit in (0, {terms.window:.0f}]")
    out: list[float] = []
    for launch in launches:
        samples = [
            (float(t), float(price))
            for t, price in launch["samples"]
            if float(t) <= clock
        ]
        out.append(settle_linear(samples, terms).velocity_per_minute)
    return out


def tertile_edges(values: list[float]) -> tuple[float, float]:
    """Last value in the first third, and last value in the second third."""
    ordered = sorted(values)
    n = len(ordered)
    if n < 9 or n % 3 != 0:
        raise ValueError(f"tertile edges need a multiple of 3 tapes, at least 9, got {n}")
    third = n // 3
    low = ordered[third - 1]
    high = ordered[2 * third - 1]
    if not low < high:
        raise ValueError("tertile edges are not separated")
    return low, high


def _rank_bin(payoffs: list[float]) -> RankBin:
    return RankBin(
        n=len(payoffs),
        mean_payoff=_mean(payoffs),
        stderr=_stderr_of_mean(payoffs),
    )


def _assign(velocity: float, low: float, high: float) -> int:
    if velocity <= low:
        return 0
    if velocity <= high:
        return 1
    return 2


def frozen_rank(
    reference: list[dict],
    replication: list[dict],
    terms: LinearTerms,
    clock: float = FROZEN_RANK_CLOCK,
    low_cut: float = FROZEN_RANK_LOW,
    high_cut: float = FROZEN_RANK_HIGH,
) -> FrozenRank:
    """Score both windows on cuts taken from the reference sample only.

    Bin 0 is frozen velocity at or below the low cut, bin 1 is between the
    cuts, bin 2 is above the high cut. Payoffs are the finished tape.
    """
    if not low_cut < high_cut:
        raise ValueError("cuts must be ordered")
    if len(reference) < 8 or len(replication) < 8:
        raise ValueError("each window needs at least 8 tapes")
    return FrozenRank(
        clock=clock,
        low_cut=low_cut,
        high_cut=high_cut,
        reference=_bin_payoffs(reference, terms, clock, low_cut, high_cut),
        replication=_bin_payoffs(replication, terms, clock, low_cut, high_cut),
    )


def _bin_payoffs(
    launches: list[dict],
    terms: LinearTerms,
    clock: float,
    low_cut: float,
    high_cut: float,
) -> tuple[RankBin, RankBin, RankBin]:
    velocities = frozen_velocity(launches, terms, clock)
    payoffs = _payoffs(launches, terms, None)
    buckets: list[list[float]] = [[], [], []]
    for velocity, payoff in zip(velocities, payoffs):
        buckets[_assign(velocity, low_cut, high_cut)].append(payoff)
    return (_rank_bin(buckets[0]), _rank_bin(buckets[1]), _rank_bin(buckets[2]))

