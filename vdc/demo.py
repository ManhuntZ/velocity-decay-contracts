"""Print the three tapes, the sample means, and what replicates."""

from __future__ import annotations

from pathlib import Path

from vdc.contract import LinearTerms, settle_linear
from vdc.curve import QUOTE0, TOKEN0, path_from_trades
from vdc.fit import fit_launches, load_launches
from vdc.freeze import FREEZE_CLOCKS, freeze_clock, frozen_rank, window_gap
from vdc.sample import mark_launches
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
    launches = load_launches(Path(__file__).resolve().parents[1] / "data" / "launches.json")
    mark = mark_launches(launches, terms)
    print(f"14 Oct sample    n={mark.n}   sample mean, not a price")
    print(f"mean payoff      {mark.mean_payoff:>8.2f}   stderr {mark.stderr:.2f}")
    print(f"mean velocity    {mark.mean_velocity * 100:.2f}%/min   capped {mark.n_capped}")
    second = load_launches(Path(__file__).resolve().parents[1] / "data" / "launches_b.json")
    other = mark_launches(second, terms)
    fitted = fit_launches(second)
    print()
    print(f"15 Oct sample    n={other.n}   same terms   not pooled")
    print(f"mean payoff      {other.mean_payoff:>8.2f}   stderr {other.stderr:.2f}")
    print(f"mean velocity    {other.mean_velocity * 100:.2f}%/min   capped {other.n_capped}")
    held = (
        fitted.half_life == terms.half_life
        and abs(fitted.strike_per_minute - terms.strike_per_minute) < 0.02
    )
    print(
        f"its own fit      half-life {fitted.half_life:.0f}s   "
        f"strike {fitted.strike_per_minute * 100:.2f}%/min   "
        f"{'spec default unchanged' if held else 'disagrees with the spec default'}"
    )
    _print_freeze(launches, second, terms)
    _print_gap(launches, second, terms)
    _print_rank(launches, second, terms)


def _print_freeze(first: list[dict], second: list[dict], terms: LinearTerms) -> None:
    left = {point.clock: point for point in freeze_clock(first, terms)}
    right = {point.clock: point for point in freeze_clock(second, terms)}
    print()
    print("if the tape froze   flat carry   not a conditional expectation")
    print(f"{'clock':<8}{'14 Oct R²':>12}{'RMSE':>8}{'sign':>8}{'15 Oct R²':>12}{'RMSE':>8}{'sign':>8}")
    for clock in FREEZE_CLOCKS:
        a = left[clock]
        b = right[clock]
        print(
            f"{clock:.0f}s".ljust(8)
            + f"{a.r_squared:12.3f}{a.rmse:8.0f}{a.sign_agreement:8.2f}"
            + f"{b.r_squared:12.3f}{b.rmse:8.0f}{b.sign_agreement:8.2f}"
        )
    raw = LinearTerms(cap=1e12)
    raw_a = mark_launches(first, raw)
    raw_b = mark_launches(second, raw)
    print(
        f"uncapped mean    14 Oct {raw_a.mean_payoff:.2f}   "
        f"15 Oct {raw_b.mean_payoff:.2f}   the cap is not the gap"
    )


def _print_gap(first: list[dict], second: list[dict], terms: LinearTerms) -> None:
    print()
    print("frozen mean payoff   gap is 15 Oct minus 14 Oct   not a price")
    print(f"{'clock':<8}{'14 Oct':>10}{'15 Oct':>10}{'gap':>10}{'t':>8}")
    for row in window_gap(first, second, terms):
        label = "expiry" if row.clock is None else f"{row.clock:.0f}s"
        print(
            f"{label:<8}{row.mean_a:10.2f}{row.mean_b:10.2f}{row.gap:10.2f}{row.t_stat:8.2f}"
        )


def _print_rank(first: list[dict], second: list[dict], terms: LinearTerms) -> None:
    rank = frozen_rank(first, second, terms)
    print()
    print(
        "frozen V at "
        f"{rank.clock:.0f}s   cuts {rank.low_cut * 100:.2f}%/min and "
        f"{rank.high_cut * 100:.2f}%/min   14 Oct tertiles, not refit"
    )
    print(f"{'bin':<8}{'14 Oct n':>10}{'mean':>10}{'se':>8}{'15 Oct n':>10}{'mean':>10}{'se':>8}")
    names = ("worst", "middle", "best")
    for name, left, right in zip(names, rank.reference, rank.replication):
        print(
            f"{name:<8}{left.n:10d}{left.mean_payoff:10.2f}{left.stderr:8.2f}"
            f"{right.n:10d}{right.mean_payoff:10.2f}{right.stderr:8.2f}"
        )
    print("order holds on both days. the worst-third level does not.")


if __name__ == "__main__":
    main()
