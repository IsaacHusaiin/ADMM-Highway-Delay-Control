## What this is
We tested how changing the **initial ramp queue** affects ADMM, while keeping:

- `meter_capacity = 0.9 * observed_release`
- `alpha_main = 10`
- `beta_local = 3`
- `gamma = 2`
- `eta = 0.7`
- `lambda_1 = 1`
- `lambda_2 = 0.5`
- `lambda_3 = 1`
- `lambda_4 = 0.5`
- `arrival_multiplier = 1.5`

Tested cases:

- `0% of ramp max queue`
- `25% of ramp max queue`
- `50% of ramp max queue`

## Why we are doing this
The initial ramp queue represents how many vehicles are already waiting on the ramps at the start of the horizon.

Goal:
- see whether ADMM is sensitive to starting ramp congestion
- check the effect on freeway delay, local delay, fairness, and spillback

---

## Baseline (same freeway state, different initial ramp queue)

| Initial Queue | Mainline Delay Before | Local Delay Before | Fairness Before | Doorway Before | Safe Before | Spillback Before | Total Capacity Before |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0%  | 26532.175 | 15101.550 | 57.361 | 5090.232 | 265407.689 | 2852.625 | 273350.545 |
| 25% | 26532.175 | 15791.850 | 24.284 | 5090.232 | 265407.689 | 2957.683 | 273455.603 |
| 50% | 26532.175 | 16284.775 | 7.155  | 5090.232 | 265407.689 | 3060.608 | 273558.528 |

---

## Results Table

| Initial Queue | Mainline Delay (After) | Local Delay (After) | Fairness (After) | Doorway Penalty (After) | Safe Penalty (After) | Spillback Penalty (After) | Total Capacity Penalty (After) | Normalized Weighted Objective (After) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0%  | 15046.948 | 15406.420 | 44.459 | 2496.959 | 0.000 | 4219.089 | 6716.048 | 11.512 |
| 25% | 15101.193 | 15966.780 | 18.549 | 2512.237 | 0.000 | 4343.453 | 6855.690 | 11.480 |
| 50% | 15166.818 | 16365.995 | 5.291  | 2520.135 | 0.000 | 4464.902 | 6985.036 | 11.435 |

---

## Main observations
- Increasing the initial ramp queue has **little effect on freeway performance**
- Mainline delay after ADMM changes only slightly:
  - `15046.948 -> 15101.193 -> 15166.818`
- Local delay increases clearly as initial queue increases
- Spillback also increases slightly
- Safe-threshold penalty remains `0` in all tested cases

## Important note about fairness
The fairness penalty becomes much smaller as initial ramp queue increases.

This does **not automatically mean the system is healthier**.

It mainly means:
- ramps start with more similar stress levels
- so the difference between ramp stresses becomes smaller

So lower fairness here may partly reflect **more uniform congestion**, not necessarily better overall conditions.

## Interpretation
This test suggests:
- initial ramp queue mostly affects the **ramp side**
- freeway-side performance is relatively robust in the tested range
- ADMM still keeps safe-threshold violations at zero

## Final conclusion
In the current model, changing the initial ramp queue from `0%` to `50%` of ramp storage has only a small effect on mainline delay, but it increases local delay and spillback. The ADMM solution remains freeway-protective, while the fairness term becomes smaller because ramp stress becomes more similar across ramps.
