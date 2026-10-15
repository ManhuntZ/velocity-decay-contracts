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
