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

## Sample means

The 14 Oct figure is the mean payoff to the long on the 33 tapes, settled at the spec default. One of those tapes hits the cap. It is a sample mean. It is not a price.

| | |
| --- | ---: |
| mean payoff | −131.13 |
| standard error of the mean | 56.18 |
| mean V | −16.96%/min |
| tapes at the cap | 1 |

`python -m vdc` prints that number. The standard error is 56, so another afternoon moves it. The next section is why it is not averaged with the second window.

## Second window

Thirty more SOL bonding curves, created 15 Oct 2026 between 03:37 and 03:44 UTC. Same filters: SOL quote, at least 0.005 SOL in the curve, at least six prints, a print within 45 seconds of creation. No mint in common with the first 33. The burst is seven minutes, not another full hour. That is how fast the filter filled.

Time reversal still picks 2 minutes.

| half-life | t |
| --- | ---: |
| 2 min | 2.46 |
| 5 min | 2.41 |
| 10 min | 2.34 |
| flat | 0 |

The 60th percentile on this window is **−4.47%/min**, about one point from the locked −3.36. That is not a new contract. The spec default stays.

Settled on the locked terms, the window pays **−363.59** to the long. Standard error of the mean 91.96. Ten tapes hit the cap. Mean `V` is −58.5%/min. The first window's −131 does not replicate. The kernel and the strike did. The left tail did not.

The two windows are not pooled. A blend would look more precise and would hide the disagreement.

## If the tape froze

The inception means are −131 and −364. Lift the cap and they are **−136.00** and **−551.55**. Ten tapes on the second window were truncated at collateral, so the clamp was hiding left tail, not creating the gap. The second window is worse without the cap.

Drop every print after a clock and settle what is left, flat-carrying to 15 minutes. R² is one minus the residual sum of squares over the total sum of squares of the final payoff. RMSE is in desk units. Sign is the share of tapes that finish on the same side of zero.

| clock | 14 Oct R² | RMSE | sign | 15 Oct R² | RMSE | sign |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 30s | 0.351 | 256 | 0.79 | −0.021 | 500 | 0.73 |
| 60s | 0.576 | 207 | 0.88 | 0.783 | 231 | 0.83 |
| 2 min | 0.907 | 97 | 1.00 | 0.947 | 114 | 0.90 |
| 5 min | 0.998 | 15 | 1.00 | 0.999 | 15 | 0.97 |

By one half-life, that counterfactual explains about 91% and 95% of final-payoff variance on the two windows. At 30 seconds it does not. On the second window the frozen payoff is slightly worse than guessing the mean.

This is not a conditional expectation, and it is not "the contract is finished." Three tapes on 15 Oct still have the wrong sign at two minutes. One tape on 14 Oct is positive if frozen at three minutes and finishes about 109 in the other direction. The canned late tape is a different object again: nothing has printed by two minutes, so a freeze there pays the strike and the real payoff arrives later.

Half-life and strike stay the 14 Oct fit. The windows stay unpooled.

## What replicates

The two sample means are not a price. Flat-carry the tapes and the disagreement is already in before expiry. The gap is 15 Oct minus 14 Oct. The t-statistic is that gap divided by the standard error of the difference of means.

| clock | 14 Oct | 15 Oct | gap | t |
| --- | ---: | ---: | ---: | ---: |
| 30s | −25.02 | −122.69 | −97.67 | −1.19 |
| 60s | −64.60 | −261.35 | −196.75 | −2.02 |
| 2 min | −101.11 | −318.41 | −217.30 | −2.17 |
| expiry | −131.13 | −363.59 | −232.46 | −2.16 |

At 30 seconds the days are not separated. At 60 seconds they are, and the gap is already the expiry gap. Another unconditional window would print a third mean. It would not say which one to quote.

What keeps its sign is the rank of frozen velocity at two minutes. The cuts are the tertile edges of the 14 Oct tapes only, thirds of 11: **−19.02%/min** and **−0.52%/min**. A later window is scored on these cuts. They are not refit.

| frozen V at 2 min | 14 Oct | 15 Oct |
| --- | ---: | ---: |
| at or below −19.02%/min | −466.36 ± 99.74 (n=11) | −942.85 ± 55.31 (n=12) |
| between the cuts | −69.00 ± 18.19 (n=11) | −42.41 ± 25.88 (n=8) |
| above −0.52%/min | +141.96 ± 30.58 (n=11) | +74.57 ± 39.97 (n=10) |

Both days run worst, then middle, then best, and the top bin is positive. The worst third is negative both times and 476 apart. That level is not a price either. The middle and the top sit much closer. Do not fit a surface through the crash bucket. Do not pool the windows. Half-life and strike stay.

## Launch mark, retired

An earlier draft printed a handmade Poisson flow near +464. That simulator is still in the package, and still tested. It is not a price.

## Run

```bash
python -m vdc
python -m unittest discover -s tests
```

Python 3.10 or newer. No dependencies.
