## What this is
We tested how changing the **delay priority weights** affects ADMM, while keeping:

- `meter_capacity = 0.9 * observed_release`
- all other settings fixed

Weights tested:

- `alpha_main ∈ {5, 10, 15, 20}`
- `beta_local ∈ {1, 3, 5, 7}`

Tested pairs:

- `(5, 1)`
- `(10, 3)`
- `(15, 5)`
- `(20, 7)`

## Why we are doing this
`alpha_main` controls how much we prioritize **mainline delay**.  
`beta_local` controls how much we prioritize **local delay**.

Goal:
- check whether changing these weights changes the actual ADMM solution
- see whether the controller is sensitive to delay priorities or mostly to `meter_capacity`

---

## Baseline (same for all cases)

| Metric | Baseline |
|---|---:|
| Mainline Delay | 26532.175 |
| Local Delay | 15101.550 |
| Fairness Penalty | 57.361 |
| Doorway Penalty | 5090.232 |
| Safe Penalty | 265407.689 |
| Spillback Penalty | 2852.625 |
| Total Capacity Penalty | 273350.545 |

---

## Results Table

| `(alpha_main, beta_local)` | Mainline Delay (After) | Local Delay (After) | Fairness (After) | Doorway Penalty (After) | Safe Penalty (After) | Spillback Penalty (After) | Total Capacity Penalty (After) | Normalized Weighted Objective (After) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| (5, 1)   | 15049.029 | 15406.245 | 44.472 | 2497.252 | 0.000 | 4219.043 | 6716.295 | 6.637 |
| (10, 3)  | 15046.948 | 15406.420 | 44.459 | 2496.959 | 0.000 | 4219.089 | 6716.048 | 11.512 |
| (15, 5)  | 15044.859 | 15406.595 | 44.447 | 2496.666 | 0.000 | 4219.137 | 6715.803 | 16.386 |
| (20, 7)  | 15042.745 | 15406.772 | 44.435 | 2496.372 | 0.000 | 4219.185 | 6715.558 | 21.260 |

---

## Main observations
- The **actual ADMM results are almost identical** across all tested `(alpha_main, beta_local)` pairs
- Mainline delay changes only slightly:
  - from `15049.029` down to `15042.745`
- Local delay also changes only slightly:
  - from `15406.245` up to `15406.772`
- Fairness, doorway, spillback, and total capacity penalties are also nearly unchanged
- Safe-threshold penalty stays `0` in all cases

## Interpretation
This means that, under:

- `meter_capacity = 0.9 * observed_release`

the **controller authority** is doing most of the work.

Changing `alpha_main` and `beta_local` mainly changes:

- how the final objective is **scored**

but does **not** materially change:

- the actual optimal release decisions

## Best takeaway
In the current setup:

- `meter_capacity` matters a lot
- `alpha_main` and `beta_local` matter much less

## Recommended weight choice
A clean and defensible choice is:

- `alpha_main = 10`
- `beta_local = 3`

Reason:
- clearly prioritizes mainline over local
- not too extreme
- gives essentially the same physical result as the larger weights

## Final conclusion
For the current model, changing delay weights does **not** significantly change ADMM behavior once `meter_capacity = 0.9 * observed_release` is fixed.  
So the model is currently **much more sensitive to metering authority than to delay weights**.