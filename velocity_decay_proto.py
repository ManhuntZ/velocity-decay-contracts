"""
Velocity Decay Contracts - Minimal Prototype
Simulates price velocity check and settlement for bonding-curve tokens.
"""

import time
from typing import List, Tuple

class VelocityDecayContract:
    def __init__(self, threshold: float = 0.05, window_seconds: int = 900):
        """
        threshold: min price slope (e.g. 5% per minute average) to pay out
        window_seconds: measurement window (default 15 min)
        """
        self.threshold = threshold
        self.window = window_seconds
        self.price_points: List[Tuple[float, float]] = []  # (timestamp, price)

    def add_price(self, price: float, ts: float = None):
        if ts is None:
            ts = time.time()
        self.price_points.append((ts, price))

    def calculate_velocity(self) -> float:
        if len(self.price_points) < 2:
            return 0.0
        start_ts, start_price = self.price_points[0]
        end_ts, end_price = self.price_points[-1]
        duration = end_ts - start_ts
        if duration <= 0 or duration > self.window:
            return 0.0
        # Simple slope: fractional change per second, scaled
        velocity = (end_price - start_price) / start_price / duration
        return velocity

    def settle(self) -> dict:
        velocity = self.calculate_velocity()
        pays = velocity >= self.threshold
        payout_multiplier = max(1.0, velocity / self.threshold) if pays else 0.0
        return {
            "velocity": round(velocity, 6),
            "threshold": self.threshold,
            "pays": pays,
            "payout_multiplier": round(payout_multiplier, 2),
            "points": len(self.price_points)
        }

# Demo
if __name__ == "__main__":
    contract = VelocityDecayContract(threshold=0.0001)  # ~0.01% per sec example

    # Simulate fast pump (high velocity)
    base = time.time()
    contract.add_price(1.0, base)
    contract.add_price(1.08, base + 300)   # +8% in 5 min
    contract.add_price(1.25, base + 600)   # continues

    result = contract.settle()
    print("High velocity example:", result)

    # Reset and slow move
    contract2 = VelocityDecayContract(threshold=0.0001)
    contract2.add_price(1.0, base)
    contract2.add_price(1.01, base + 900)
    print("Low velocity example:", contract2.settle())
