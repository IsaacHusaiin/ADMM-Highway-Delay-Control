
## What this is
We tested how changing the **fairness weight** affects ADMM, while keeping:

- `meter_capacity = 0.9 * observed_release`
- `alpha_main = 10`
- `beta_local = 3`
- all other settings fixed

Tested values:

- `gamma ∈ {0.5, 1, 2, 5}`

## Why we are doing this
`gamma` controls how much ADMM cares about **fairness across ramps**.

Goal:
- check whether increasing fairness importance changes the actual ADMM solution
- see the tradeoff between fairness, mainline delay, local delay, and spillback

---

## Baseline (same for all cases)

| Metric | Baseline |
|---|---:|
| Mainline Delay | 26532.175 |
| Local Delay | 15101.550 |
| Doorway Penalty | 5090.232 |
| Safe Penalty | 265407.689 |
| Spillback Penalty | 2852.625 |
| Total Capacity Penalty | 273350.545 |

> Fairness baseline changes with `gamma`, so it is shown inside the results table.

---

## Results Table

| `gamma` | Fairness Penalty Before | Mainline Delay (After) | Local Delay (After) | Fairness Penalty (After) | Doorway Penalty (After) | Safe Penalty (After) | Spillback Penalty (After) | Total Capacity Penalty (After) | Normalized Weighted Objective (After) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5 | 14.340 | 15232.647 | 15388.007 | 11.528 | 2524.579 | 0.000 | 4215.258 | 6739.837 | 10.435 |
| 1.0 | 28.680 | 15166.114 | 15394.438 | 22.762 | 2512.511 | 0.000 | 4216.387 | 6728.898 | 10.801 |
| 2.0 | 57.361 | 15046.948 | 15406.420 | 44.459 | 2496.959 | 0.000 | 4219.089 | 6716.048 | 11.512 |
| 5.0 | 143.402 | 14741.562 | 15437.376 | 104.414 | 2435.586 | 0.000 | 4228.096 | 6663.682 | 13.483 |

---

## Main observations
- Increasing `gamma` causes **moderate** changes in the ADMM solution
- Higher `gamma` gives:
  - slightly lower **mainline delay**
  - slightly lower **doorway penalty**
  - slightly lower **total capacity penalty**
- But higher `gamma` also gives:
  - slightly higher **local delay**
  - slightly higher **spillback penalty**

## Important note
The printed fairness penalty increases with `gamma` because the term itself is weighted by `gamma`.

So the point of this test is not the raw fairness number alone, but how changing fairness importance shifts the overall tradeoff.

## Interpretation
Compared to earlier tests:

- `meter_capacity` had the **largest effect**
- `gamma` has a **moderate effect**
- `alpha_main` and `beta_local` had only a **small effect** in the tested ranges

So fairness matters, but controller authority still matters much more.

## Recommended choice
A clean and balanced setting is:

- `gamma = 2`

Reason:
- fairness is given meaningful importance
- mainline still improves well
- local/spillback costs remain small
- easier to defend than `gamma = 5`

## Final conclusion
With `meter_capacity = 0.9 * observed_release`, increasing `gamma` changes the ADMM solution moderately. Higher fairness weight slightly improves freeway-side performance and doorway penalty, while slightly worsening local delay and spillback. Safe-threshold penalty remains zero for all tested values.

