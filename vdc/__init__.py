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
from vdc.flow import FRONT_LOADED, Flow, monte_carlo_linear, simulate_flow
from vdc.scenarios import BUY_SIZES, SCENARIOS, late_trades, grind_trades, sniper_trades
from vdc.velocity import (
    Velocity,
    arithmetic_slope_per_minute,
    decay_weighted_velocity,
    log_slope_per_minute,
    prepare_path,
)

__version__ = "0.2.0"

__all__ = [
    "BUY_SIZES",
    "BondingCurve",
    "DigitalSettlement",
    "DigitalTerms",
    "FRONT_LOADED",
    "Flow",
    "LinearTerms",
    "Print",
    "QUOTE0",
    "SCENARIOS",
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
