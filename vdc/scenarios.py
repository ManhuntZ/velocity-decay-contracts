"""Three tapes. Same quote in, same terminal spot, different timing."""

from __future__ import annotations

BUY_SIZES = (400.0, 250.0, 120.0)  # 770 quote


def sniper_trades() -> tuple[tuple[str, float, float], ...]:
    times = (8.0, 20.0, 45.0)
    return tuple(("buy", t, size) for t, size in zip(times, BUY_SIZES))


def grind_trades() -> tuple[tuple[str, float, float], ...]:
    # 11 × 70 = 770, spread through the first 11 minutes
    return tuple(("buy", 60.0 * (i + 1), 70.0) for i in range(11))


def late_trades() -> tuple[tuple[str, float, float], ...]:
    times = (660.0, 780.0, 870.0)
    return tuple(("buy", t, size) for t, size in zip(times, BUY_SIZES))


SCENARIOS = {
    "sniper": sniper_trades,
    "grind": grind_trades,
    "late": late_trades,
}
