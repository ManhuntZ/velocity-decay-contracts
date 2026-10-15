"""Sample means on the shipped tapes.

Mean payoff to the long, and the standard error of that mean, settled under
the contract terms. A sample mean is not a price. The Poisson flow is a
simulator. It is not a sample mean either.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from vdc.contract import LinearTerms, settle_linear

SAMPLE_WINDOW = 900.0


@dataclass(frozen=True)
class SampleMark:
    n: int
    mean_payoff: float
    stderr: float
    mean_velocity: float
    n_capped: int


def mark_launches(launches: list[dict], terms: LinearTerms) -> SampleMark:
    if terms.window != SAMPLE_WINDOW:
        raise ValueError(f"sample window is {SAMPLE_WINDOW:.0f}s, got {terms.window}")
    if len(launches) < 8:
        raise ValueError(f"need at least 8 tapes, got {len(launches)}")
    payoffs: list[float] = []
    velocities: list[float] = []
    n_capped = 0
    for launch in launches:
        samples = [(float(t), float(price)) for t, price in launch["samples"]]
        settled = settle_linear(samples, terms)
        payoffs.append(settled.payoff_to_long)
        velocities.append(settled.velocity_per_minute)
        n_capped += int(settled.capped)
    n = len(payoffs)
    mean = sum(payoffs) / n
    var = sum((payoff - mean) ** 2 for payoff in payoffs) / (n - 1)
    return SampleMark(
        n=n,
        mean_payoff=mean,
        stderr=math.sqrt(var / n),
        mean_velocity=sum(velocities) / n,
        n_capped=n_capped,
    )
