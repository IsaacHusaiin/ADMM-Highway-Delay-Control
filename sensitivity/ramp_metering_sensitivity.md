
## What this is
We tested how much **ADMM improves the corridor** when we change:

- `meter_capacity = observed_release * c`
- where `c ∈ {1.0, 0.95, 0.90, 0.85, 0.80}`

## Why we are doing this
`meter_capacity` controls how much authority ADMM has to meter the ramps.

- `1.0` = ADMM can release up to the observed amount
- smaller values = ADMM can meter more aggressively
- goal: see whether stronger metering gives better freeway performance, and what tradeoff happens on the ramp/local side

## Fixed setup
- `q_in_boundary = 64.5`
- `X_safe = 0.7 * N_max`
- normalized weighted objective used for comparison

---

## Results Table

| meter_capacity | Mainline Delay (After) | Local Delay (After) | Fairness (After) | Doorway Penalty (After) | Safe Penalty (After) | Spillback Penalty (After) | Total Capacity Penalty (After) | Normalized Weighted Objective (After) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.00 | 25901.099 | 15173.548 | 51.865 | 4933.118 | 245430.195 | 2868.572 | 253231.885 | 28.291 |
| 0.95 | 20482.259 | 15300.122 | 48.117 | 3394.852 | 100.150 | 3514.863 | 7009.865 | 23.466 |
| 0.90 | 15037.861 | 15407.179 | 44.406 | 2495.704 | 0.000 | 4219.300 | 6715.004 | 19.215 |
| 0.85 | 9786.470 | 15499.924 | 41.585 | 1953.035 | 0.000 | 4998.350 | 6951.385 | 15.219 |
| 0.80 | 6487.982 | 15579.914 | 38.822 | 1560.687 | 0.000 | 5838.590 | 7399.277 | 12.733 |

---

## Baseline (same for all comparisons)

| Metric | Baseline |
|---|---:|
| Mainline Delay | 26532.175 |
| Local Delay | 15101.550 |
| Fairness Penalty | 57.361 |
| Doorway Penalty | 5090.232 |
| Safe Penalty | 265407.689 |
| Spillback Penalty | 2852.625 |
| Total Capacity Penalty | 273350.545 |
| Normalized Weighted Objective | 29.000 |

---

## Main observations
- As `meter_capacity` decreases, **ADMM becomes much stronger**
- Lower `meter_capacity` gives:
  - much lower **mainline delay**
  - much lower **doorway penalty**
  - much lower **safe-threshold penalty**
  - better **fairness**
- But lower `meter_capacity` also gives:
  - higher **local delay**
  - higher **spillback penalty**

## Best interpretation
- `1.0` = weak control
- `0.95` = moderate improvement
- `0.90` = strong balanced case
- `0.85` and `0.80` = aggressive control, best freeway improvement, but more ramp-side cost

## Best candidate
**`meter_capacity = 0.90 * observed_release`** looks like the best balance because:

- safe penalty becomes `0`
- mainline delay drops a lot
- doorway penalty drops a lot
- spillback increases, but not as badly as `0.85` or `0.80`

## Extreme aggressive case
**`meter_capacity = 0.80 * observed_release`** gives the strongest freeway improvement, but also the largest spillback increase.


## NOTE
1. we can lower the `meter_capacity` to even smaller number . however , it will create massive spillback and starts to create traffic in local roads . our goal is to find the balance , not extreme result . 
2. if we keep the `meter_capacity` = observed_release * 0.9 , safe_threshold_penalty becomes 0. 




## 



## **2.**

**`alpha_main`**

This changes how much ADMM cares about mainline delay.

Test:

- `10`
- `15`
- `20`
- `30`

Higher = more aggressive freeway protection.

---

## 

## **3.**

**`beta_local`**

This changes how much ADMM cares about local delay.

Test:

- `2`
- `5`
- `8`
- `10`

Higher = ADMM becomes more careful about ramp queues.

---

## 

## **4.**

**`gamma`**

This changes fairness importance.

Test:

- `0.5`
- `1`
- `2`
- `5`

Higher = more balanced treatment across ramps.

---

## 

## **5.**

**`eta`**

This changes safe-threshold tightness.

Test:

- `0.75`
- `0.70`
- `0.65`
- `0.60`

Lower = safe penalty activates more.

Do **not** go too low like `0.3` unless stress testing.

---

## 

## **6.**

**`lambda_1`**

Doorway penalty weight.

Test:

- `0.5`
- `1`
- `2`
- `5`

---

## 

## **7.**

**`lambda_2`**

Safe-threshold penalty weight.

Test:

- `0.1`
- `0.5`
- `1`
- `2`

---

## 

## **8.**

**`lambda_4`**

Spillback penalty weight.

Test:

- `0.1`
- `0.5`
- `1`
- `2`

---

## 

## **9.**

**`q_in_boundary`**

You tested one jump already. Still worth checking a range.

Test:

- `60`
- `64.5`
- `70`
- `75`

---

## 

## **10.**

**`arrival_multiplier`**

This changes ramp demand pressure.

Test:

- `1.2`
- `1.5`
- `1.8`
- `2.0`

Higher = more local pressure, more spillback risk.

---

## 

## **11.**

**`ramp_queue_0`**

Initial ramp queues.

Test:

- all `0`
- all `25% of R_max`
- all `50% of R_max`

This tells you if ADMM behaves differently when ramps start partially loaded.

---

## 

## **12.**

**`mainline_initial_state`**

Try heavier initial freeway congestion.

For example:

- current state
- `1.1 * current`
- `1.2 * current`

That tests whether ADMM helps more under worse starting congestion.

---

## 

## **13.**

**`rho`**

ADMM tuning parameter.

Test:

- `1`
- `2`
- `5`
- `10`

This affects convergence behavior, not traffic physics directly.

---

## 

## **14.**

**`max_admm_iters`**

Test:

- `20`
- `50`
- `100`

Just to make sure ADMM is not stopping too early.

---

## **Best order to try everything**

Do it like this:

1. `meter_capacity`
2. `alpha_main`
3. `beta_local`
4. `eta`
5. `lambda_1`
6. `lambda_2`
7. `lambda_4`
8. `gamma`
9. `arrival_multiplier`
10. `q_in_boundary`
11. `ramp_queue_0`
12. `mainline_initial_state`
13. `rho`
14. `max_admm_iters`

## **What to record each time**

For every test, track:

- mainline delay
- local delay
- fairness penalty
- doorway penalty
- safe penalty
- spillback penalty
- normalized weighted total objective
- average release ratio per ramp

If you want, I can give you a clean experiment table template next.