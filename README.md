# Velocity Decay Contracts

A velocity decay contract pays on **how fast** a bonding-curve token's price moved in a fixed window after launch, not on where it finished. Early prints are worth more than late ones. Both sides post collateral. Settlement is cash, in desk units.

This is a research prototype. It is not a venue, not on-chain, and not a forecast.

## Settlement

Log-velocity is the slope of log price. Between prints it is constant. After the last print it is zero out to expiry (flat carry). Prints outside the window are ignored. A print at `t = 0` is required.

```text
λ = ln(2) / half_life
w(t) = exp(−λ t)
V = ∫ v(t) w(t) dt  /  ∫ w(t) dt        v(t) = d/dt ln P(t)
```

`V` is reported per minute. An infinite half-life is a flat kernel: `V` equals the log slope and timing drops out.

Linear payoff, what the long receives from the short:

```text
clamp(notional · (V − K), −cap, cap)
```

Each side posts `cap`. The clamp is what makes that collateral enough.

Digital: the long pays `premium` at inception, the short posts `payout − premium`, and the long is paid `payout` if `V ≥ K`. The premium has to sit strictly inside the payout.

## Why the first sketch does not settle

The first file priced `(P_end − P_start) / P_start / duration`, returned 0 when the tape ran past the window, and paid an uncapped multiple. That ignores the path, throws away a finished tape, and has no collateral. `velocity_decay_proto.py` still runs. It now calls this package.

## Three tapes, one terminal price

Constant-product curve, no fee. Reserves start at `1,000` quote and `1,000,000` token. Each tape buys **770** quote, so they share an end spot. Order does not change the terminal price. It changes `V`.

Window 900s, half-life 300s, strike 10%/min (above the log slope), notional 1,000, cap 1,000.

| path | multiple | log slope | sketch slope | contract V | payoff to long |
| --- | ---: | ---: | ---: | ---: | ---: |
| sniper — buys at 0:08, 0:20, 0:45 | 3.133× | 7.61%/min | 14.22%/min | 17.67%/min | +76.68 |
| grind — 70 quote each minute | 3.133× | 7.61%/min | 14.22%/min | 9.94%/min | −0.60 |
| late — same clips at 11:00, 13:00, 14:30 | 3.133× | 7.61%/min | 14.22%/min | 6.79%/min | −32.09 |

The long is not paid for finishing up. The long is paid for the move happening early. On a flat kernel the three contract velocities are the same number.

## Launch mark

Buys arrive as an inhomogeneous Poisson process, intensity `0.35 · exp(−t/90)`, lognormal size with median 40. Sells start at 120s and are smaller. That measure (n=200, seed 7) marks this 15-minute contract at about **+119.8** to the long, stderr about 2.9. It is hotter than the canned sniper tape. It is a pricing measure, not a prediction.

## Run

```bash
python -m vdc
python -m unittest discover -s tests
```

Python 3.10 or newer. No dependencies.
