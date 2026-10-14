"""Print the three tapes and a launch mark."""

from __future__ import annotations

from vdc.contract import LinearTerms, settle_linear
from vdc.curve import QUOTE0, TOKEN0, path_from_trades
from vdc.flow import FRONT_LOADED, monte_carlo_linear
from vdc.scenarios import SCENARIOS


def _samples(name: str, window: float):
    prints = path_from_trades(QUOTE0, TOKEN0, SCENARIOS[name](), window)
    return [(p.t, p.price) for p in prints]


def main() -> None:
    terms = LinearTerms()
    print("VELOCITY DECAY")
    print(
        f"window {terms.window:.0f}s   half-life {terms.half_life:.0f}s   "
        f"strike {terms.strike_per_minute * 100:.2f}%/min   "
        f"notional {terms.notional:.0f}   cap {terms.cap:.0f}"
    )
    print()
    header = f"{'path':<10}{'multiple':>10}{'log slope':>12}{'sketch':>12}{'contract V':>12}{'payoff':>12}"
    print(header)
    for name in ("sniper", "grind", "late"):
        settled = settle_linear(_samples(name, terms.window), terms)
        multiple = settled.price_end / settled.price_start
        print(
            f"{name:<10}"
            f"{multiple:>10.3f}"
            f"{settled.log_slope_per_minute * 100:>11.2f}%"
            f"{settled.arithmetic_slope_per_minute * 100:>11.2f}%"
            f"{settled.velocity_per_minute * 100:>11.2f}%"
            f"{settled.payoff_to_long:>12.2f}"
        )
    print()
    mark = monte_carlo_linear(QUOTE0, TOKEN0, FRONT_LOADED, terms, n=200, seed=7)
    print("toy flow         front-loaded Poisson, not the 33-tape sample")
    print(f"                 n={mark.n}  seed=7")
    print(f"fair to long     {mark.fair_to_long:>8.2f}   stderr {mark.stderr:.2f}")
    print(f"mean velocity    {mark.mean_velocity * 100:.2f}%/min")


if __name__ == "__main__":
    main()
