# Velocity Decay Contracts

A velocity decay contract pays on **how fast** a bonding-curve token's price moved in a fixed window after launch, not on where it finished. Early prints are worth more than late ones. Both sides post collateral. Settlement is cash, in desk units.

This is a research prototype. It is not a venue, not on-chain, and not a forecast. The half-life and strike below are one afternoon of pump.fun on 14 Oct 2026. They are not a regime. Rerun the fit.

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

## Spec default

Half-life 5 minutes and strike +10%/min were a demo choice. They split three handmade tapes. They are not the spec.

The spec is fit on `data/launches.json`: 33 pump.fun SOL bonding curves, first 15 minutes only, fetched 14 Oct 2026 17:25 UTC. Price is SOL, so a drift in SOL does not enter `V`. A tape needs at least six prints and a print within 45 seconds of creation. Mints stay in the file so the sample can be audited. Names do not.

The kernel is chosen by time reversal. Reverse the order of the log returns. Keep the interval lengths and the total log return. A flat kernel is invariant to that: the mean gap is numerical noise and its t-statistic is forced to 0. A decay kernel is not. The score is the mean of `V_forward − V_reversed`, divided by the standard error of that gap. The finite half-life with the largest absolute t-statistic wins.

| half-life | mean gap, per minute | sd | t |
| --- | ---: | ---: | ---: |
| 2 min | 0.0720 | 0.179 | 2.31 |
| 5 min | 0.0226 | 0.065 | 2.00 |
| 10 min | 0.0096 | 0.031 | 1.80 |
| flat | ~0 | ~0 | 0 |

Two minutes wins. The same order holds on the 26 tapes whose absolute log return is at least 0.2.

Do not pick the half-life by a partial correlation with clock-time earliness. On this sample almost every launch is already front-loaded, so that score has no contrast. Residualizing on the log slope flips the sign. That is collinearity, not a finding that early prints are dumps.

The strike is the 60th percentile of 2-minute `V`, so the contract is not a 5¢ or 95¢ digital. On this sample that percentile is **−3.36%/min** (`-0.03364949456289831`). Thirteen of the 33 tapes finish at or above it (39.4%). The 10th, 50th, 60th, and 90th percentiles of `V` are about −58.1%, −11.3%, −3.36%, and +11.8% per minute. The median log return is about −0.47. A negative strike is the result: this hour mostly faded. The old +10%/min strike would almost never have paid the long.

`LinearTerms` defaults are those two numbers. `tests/test_fit.py` recomputes the fit from `data/launches.json` and checks that the defaults still match.

## Three tapes, one terminal price

Constant-product curve, no fee. Reserves start at `1,000` quote and `1,000,000` token. Each tape buys **770** quote, so they share an end spot. Order does not change the terminal price. It changes `V`. These tapes are the path-identity fixture. They are not the sample the strike was fit on.

Window 900s, half-life 120s, strike −3.36%/min, notional 1,000, cap 1,000. That is what `python -m vdc` prints.

| path | multiple | log slope | sketch slope | contract V | payoff to long |
| --- | ---: | ---: | ---: | ---: | ---: |
| sniper — buys at 0:08, 0:20, 0:45 | 3.133× | 7.61%/min | 14.22%/min | 37.54%/min | +409.07 |
| grind — 70 quote each minute | 3.133× | 7.61%/min | 14.22%/min | 11.80%/min | +151.65 |
| late — same clips at 11:00, 13:00, 14:30 | 3.133× | 7.61%/min | 14.22%/min | 6.24%/min | +96.05 |

The fitted strike sits below the log slope of these canned buys, so the long is paid on all three and paid most when the buys are early. On a flat kernel the three contract velocities collapse to the log slope.

## Launch mark

`python -m vdc` still prices a handmade front-loaded Poisson flow: buys at intensity `0.35 · exp(−t/90)`, lognormal size with median 40, sells from 120s. Under the fitted strike, n=200, seed 7, that toy marks about **+463.8** to the long, stderr about 5.5, mean `V` about 43%/min.

That is not the mean payoff on the 33 tapes, and it is not a market. The strike is empirical. The flow is not. Collateral and settlement are already specified. A mark on the empirical distribution is a later step.

## Run

```bash
python -m vdc
python -m unittest discover -s tests
```

Python 3.10 or newer. No dependencies.
