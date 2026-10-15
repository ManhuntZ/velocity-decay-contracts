"""Velocity Decay Contracts — cash-settled velocity on a bonding-curve launch."""

from vdc.contract import (
    DigitalSettlement,
    DigitalTerms,
    LinearTerms,
    Settlement,
    settle_digital,
    settle_linear,
)
from vdc.curve import QUOTE0, TOKEN0, BondingCurve, Print, path_from_trades
from vdc.fit import Fit, KernelScore, fit_launches, load_launches
from vdc.flow import FRONT_LOADED, Flow, monte_carlo_linear, simulate_flow
from vdc.sample import SAMPLE_WINDOW, SampleMark, mark_launches
from vdc.scenarios import BUY_SIZES, SCENARIOS, grind_trades, late_trades, sniper_trades
from vdc.velocity import (
    Velocity,
    arithmetic_slope_per_minute,
    decay_weighted_velocity,
    log_slope_per_minute,
    prepare_path,
)

__version__ = "0.3.2"

__all__ = [
    "BUY_SIZES",
    "BondingCurve",
    "DigitalSettlement",
    "DigitalTerms",
    "FRONT_LOADED",
    "Flow",
    "Fit",
    "KernelScore",
    "fit_launches",
    "load_launches",
    "LinearTerms",
    "Print",
    "QUOTE0",
    "SCENARIOS",
    "SAMPLE_WINDOW",
    "SampleMark",
    "mark_launches",
    "Settlement",
    "TOKEN0",
    "Velocity",
    "arithmetic_slope_per_minute",
    "decay_weighted_velocity",
    "grind_trades",
    "late_trades",
    "log_slope_per_minute",
    "monte_carlo_linear",
    "path_from_trades",
    "prepare_path",
    "settle_digital",
    "settle_linear",
    "simulate_flow",
    "sniper_trades",
]
