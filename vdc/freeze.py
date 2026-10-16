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


# Absolute grid on frozen log-velocity at one half-life, in per-minute units.
# Not estimated. Not the tertile cuts. The first bin is everything at or below
# −100%/min, which the 14 Oct sample does not contain.
COMPOSITION_CLOCK = 120.0
COMPOSITION_EDGES = (-1.0, -0.5, -0.19, -0.005, 0.05)


@dataclass(frozen=True)
class VelocityCell:
    """Empty cells have mean_payoff None. A single tape has no standard error."""

    n: int
    mean_payoff: float | None
    stderr: float | None


@dataclass(frozen=True)
class CompositionBin:
    """low is None on the left tail. high is None on the right tail."""

    low: float | None
    high: float | None
    cells: tuple[VelocityCell, ...]


@dataclass(frozen=True)
class CarryMap:
    """final payoff on the flat-carry payoff at the clock. slope near 1 is the claim."""

    n: int
    slope: float
    intercept: float
    rmse: float
    residual_mean: float
    residual_stderr: float
    min_velocity: float
    max_velocity: float


@dataclass(frozen=True)
class OverlapCell:
    n: int
    mean_payoff: float
    residual_mean: float
    residual_stderr: float


@dataclass(frozen=True)
class Composition:
    clock: float
    edges: tuple[float, ...]
    bins: tuple[CompositionBin, ...]
    windows: tuple[CarryMap, ...]
    overlap_low: float
    overlap_high: float
    overlap: tuple[OverlapCell, ...]


def _pairs(
    launches: list[dict],
    terms: LinearTerms,
    clock: float,
) -> list[tuple[float, float, float]]:
    rows: list[tuple[float, float, float]] = []
    for launch in launches:
        samples = [(float(t), float(price)) for t, price in launch["samples"]]
        cut = [(t, price) for t, price in samples if t <= clock]
        frozen = settle_linear(cut, terms)
        final = settle_linear(samples, terms)
        rows.append(
            (frozen.velocity_per_minute, frozen.payoff_to_long, final.payoff_to_long)
        )
    return rows


def _edge_bin(velocity: float, edges: tuple[float, ...]) -> int:
    for index, edge in enumerate(edges):
        if velocity <= edge:
            return index
    return len(edges)


def _ols(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    n = len(xs)
    mean_x = _mean(xs)
    mean_y = _mean(ys)
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0.0:
        raise ValueError("flat-carry payoffs have no variance")
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    return slope, intercept, math.sqrt(ss_res / n)


def composition(
    windows: list[list[dict]],
    terms: LinearTerms,
    clock: float = COMPOSITION_CLOCK,
    edges: tuple[float, ...] = COMPOSITION_EDGES,
) -> Composition:
    """Whether the same frozen velocity pays the same thing on every window.

    Tertile means can disagree because a later window contains velocities the
    reference never printed. This puts every tape on one absolute grid, then
    regresses the finished payoff on the flat-carry payoff. It does not pool
    the windows into a price, and it does not move the strike.
    """
    if terms.window != 900.0:
        raise ValueError(f"composition is a 900s window, got {terms.window}")
    if len(windows) < 2:
        raise ValueError("need at least two windows")
    if len(edges) < 1 or not all(math.isfinite(edge) for edge in edges):
        raise ValueError("edges must be finite")
    if any(edges[index] >= edges[index + 1] for index in range(len(edges) - 1)):
        raise ValueError("edges must be strictly increasing")
    if not math.isfinite(clock) or clock <= 0.0 or clock > terms.window:
        raise ValueError(f"clock must sit in (0, {terms.window:.0f}]")

    paired = []
    for launches in windows:
        if len(launches) < 8:
            raise ValueError("each window needs at least 8 tapes")
        paired.append(_pairs(launches, terms, clock))

    n_bins = len(edges) + 1
    bins: list[CompositionBin] = []
    for index in range(n_bins):
        cells: list[VelocityCell] = []
        for rows in paired:
            payoffs = [
                final
                for velocity, _, final in rows
                if _edge_bin(velocity, edges) == index
            ]
            cells.append(
                VelocityCell(
                    n=len(payoffs),
                    mean_payoff=_mean(payoffs) if payoffs else None,
                    stderr=_stderr_of_mean(payoffs) if len(payoffs) >= 2 else None,
                )
            )
        bins.append(
            CompositionBin(
                low=None if index == 0 else edges[index - 1],
                high=None if index == n_bins - 1 else edges[index],
                cells=tuple(cells),
            )
        )

    maps: list[CarryMap] = []
    for rows in paired:
        frozen_pay = [frozen for _, frozen, _ in rows]
        final_pay = [final for _, _, final in rows]
        slope, intercept, rmse = _ols(frozen_pay, final_pay)
        residual = [final - frozen for _, frozen, final in rows]
        velocities = [velocity for velocity, _, _ in rows]
        maps.append(
            CarryMap(
                n=len(rows),
                slope=slope,
                intercept=intercept,
                rmse=rmse,
                residual_mean=_mean(residual),
                residual_stderr=_stderr_of_mean(residual),
                min_velocity=min(velocities),
                max_velocity=max(velocities),
            )
        )

    overlap_low = max(row.min_velocity for row in maps)
    overlap_high = min(row.max_velocity for row in maps)
    if not overlap_low < overlap_high:
        raise ValueError("frozen-velocity ranges do not overlap")
    overlap: list[OverlapCell] = []
    for rows in paired:
        kept = [
            (frozen, final)
            for velocity, frozen, final in rows
            if overlap_low <= velocity <= overlap_high
        ]
        if len(kept) < 2:
            raise ValueError("overlap needs at least 2 tapes in each window")
        finals = [final for _, final in kept]
        residual = [final - frozen for frozen, final in kept]
        overlap.append(
            OverlapCell(
                n=len(kept),
                mean_payoff=_mean(finals),
                residual_mean=_mean(residual),
                residual_stderr=_stderr_of_mean(residual),
            )
        )

    return Composition(
        clock=clock,
        edges=edges,
        bins=tuple(bins),
        windows=tuple(maps),
        overlap_low=overlap_low,
        overlap_high=overlap_high,
        overlap=tuple(overlap),
    )


# The −19%/min line is COMPOSITION_EDGES, not a new estimate. Zero is not fit.
# A tape already at the downside cap is its own state, ahead of the velocity split.
RESIDUAL_SPLIT = -0.19


@dataclass(frozen=True)
class ResidualCell:
    """mean_residual is final payoff minus flat-carry. Empty cells leave it None."""

    n: int
    mean_residual: float | None
    stderr: float | None


@dataclass(frozen=True)
class ResidualState:
    name: str
    cells: tuple[ResidualCell, ...]


@dataclass(frozen=True)
class ResidualStates:
    clock: float
    split: float
    states: tuple[ResidualState, ResidualState, ResidualState, ResidualState]


def _residual_state(velocity: float, frozen_payoff: float, cap: float, split: float) -> int:
    if frozen_payoff <= -cap + 1e-9:
        return 0
    if velocity <= split:
        return 1
    if velocity <= 0.0:
        return 2
    return 3


def residual_states(
    windows: list[list[dict]],
    terms: LinearTerms,
    clock: float = COMPOSITION_CLOCK,
    split: float = RESIDUAL_SPLIT,
) -> ResidualStates:
    """Where the leftover after the freeze is finished, and where it is not.

    State 0 is flat-carry already at the downside cap. State 1 is frozen
    velocity at or below the split and not at the cap. State 2 is between the
    split and zero. State 3 is above zero. The residual is the finished payoff
    minus flat-carry. This does not estimate a haircut and it does not move
    the strike.
    """
    if terms.window != 900.0:
        raise ValueError(f"residual states are a 900s window, got {terms.window}")
    if len(windows) < 2:
        raise ValueError("need at least two windows")
    if not math.isfinite(split) or split >= 0.0:
        raise ValueError("split must be finite and negative")
    if not math.isfinite(clock) or clock <= 0.0 or clock > terms.window:
        raise ValueError(f"clock must sit in (0, {terms.window:.0f}]")

    names = ("capped", "left", "middle", "above")
    buckets: list[list[list[float]]] = [[[] for _ in names] for _ in windows]
    for window_index, launches in enumerate(windows):
        if len(launches) < 8:
            raise ValueError("each window needs at least 8 tapes")
        for velocity, frozen_payoff, final in _pairs(launches, terms, clock):
            state = _residual_state(velocity, frozen_payoff, terms.cap, split)
            buckets[window_index][state].append(final - frozen_payoff)

    states: list[ResidualState] = []
    for state_index, name in enumerate(names):
        cells: list[ResidualCell] = []
        for window_index in range(len(windows)):
            values = buckets[window_index][state_index]
            cells.append(
                ResidualCell(
                    n=len(values),
                    mean_residual=_mean(values) if values else None,
                    stderr=_stderr_of_mean(values) if len(values) >= 2 else None,
                )
            )
        states.append(ResidualState(name=name, cells=tuple(cells)))

    return ResidualStates(
        clock=clock,
        split=split,
        states=(states[0], states[1], states[2], states[3]),
    )
