## What this is
We tested how changing the **safe-threshold tightness** affects ADMM, while keeping:

- `meter_capacity = 0.9 * observed_release`
- `alpha_main = 10`
- `beta_local = 3`
- `gamma = 2`
- all other settings fixed

Tested values:

- `eta ∈ {0.75, 0.70, 0.65, 0.60, 0.50, 0.40, 0.30}`

## Why we are doing this
`eta` controls the safe threshold:

$$
X_{safe} = \eta \cdot N_{max}
$$

So:
- larger `eta` = looser safe threshold
- smaller `eta` = tighter safe threshold

Goal:
- see when the safe-threshold penalty becomes active
- check whether changing `eta` changes the actual ADMM solution

---

## Baseline (same for all cases except Safe Penalty)

| Metric | Baseline |
|---|---:|
| Mainline Delay | 26532.175 |
| Local Delay | 15101.550 |
| Fairness Penalty | 57.361 |
| Doorway Penalty | 5090.232 |
| Physical Capacity Penalty | 0.000 |
| Spillback Penalty | 2852.625 |

> Only the **Safe Penalty** and **Total Capacity Penalty** change strongly with `eta`.

---

## Results Table

| `eta` | Safe Penalty Before | Mainline Delay (After) | Local Delay (After) | Fairness Penalty (After) | Doorway Penalty (After) | Safe Penalty (After) | Spillback Penalty (After) | Total Capacity Penalty (After) | Normalized Weighted Objective (After) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.75 | 119337.365 | 15046.948 | 15406.420 | 44.459 | 2496.959 | 0.000 | 4219.089 | 6716.048 | 11.512 |
| 0.70 | 265407.689 | 15046.948 | 15406.420 | 44.459 | 2496.959 | 0.000 | 4219.089 | 6716.048 | 11.512 |
| 0.65 | 480346.232 | 15046.948 | 15406.420 | 44.459 | 2496.959 | 0.000 | 4219.089 | 6716.048 | 11.512 |
| 0.60 | 769549.433 | 15046.948 | 15406.420 | 44.459 | 2496.959 | 600.535 | 4219.089 | 7316.583 | 11.512 |
| 0.50 | 1589185.624 | 15046.948 | 15406.420 | 44.459 | 2496.959 | 53610.111 | 4219.089 | 60326.160 | 11.529 |
| 0.40 | 2761190.763 | 15046.948 | 15406.420 | 44.459 | 2496.959 | 271528.658 | 4219.089 | 278244.706 | 11.561 |
| 0.30 | 4331124.271 | 15046.877 | 15406.423 | 44.460 | 2496.943 | 761625.891 | 4219.091 | 768341.925 | 11.600 |

---

## Main observations
- Lower `eta` makes the safe threshold tighter
- As `eta` decreases, **baseline safe penalty increases rapidly**
- The ADMM solution is almost unchanged from `eta = 0.75` down to about `eta = 0.65`
- For `eta = 0.75, 0.70, 0.65`, ADMM drives **safe penalty to zero**
- For `eta <= 0.60`, safe-threshold penalty remains active even after ADMM

## Critical calibration result
A key threshold was found:

- if `eta >= 0.627`, safe-threshold penalty is **inactive**
- if `eta < 0.627`, safe-threshold penalty becomes **active**

Interpretation:
- the corridor’s critical peak occupancy is about **62.7% of physical capacity**
- `eta = 0.627` is the transition point where the safe-threshold constraint starts to bind

## Interpretation
This means `eta` mainly changes:

- how strict the safe-threshold rule is

but it does **not** strongly change the ADMM release pattern in the current setup.

So `eta` affects:
- safe-threshold harshness a lot

but affects:
- the actual controller behavior only a little

## Recommended choice
A good practical setting is:

- `eta = 0.65` or `0.70`

Reason:
- safe threshold is meaningful
- ADMM can still eliminate safe violations
- not overly harsh or artificial

## Final conclusion
In the current model, `eta` mainly controls how hard it is to satisfy the safe-threshold condition. ADMM gives nearly the same solution for `eta = 0.75` down to `0.65`, and safe-threshold violations only start to remain after optimization when `eta` becomes tighter than about `0.627`.


