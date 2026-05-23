
## What this is
We tested how changing the **penalty multipliers** affects ADMM, while keeping:

- `meter_capacity = 0.9 * observed_release`
- `alpha_main = 10`
- `beta_local = 3`
- `gamma = 2`
- `eta = 0.7`

Tested penalty sets:

1. `(lambda_1, lambda_2, lambda_3, lambda_4) = (1, 0.5, 1, 0.5)`
2. `(lambda_1, lambda_2, lambda_3, lambda_4) = (2, 1, 3, 1)`
3. `(lambda_1, lambda_2, lambda_3, lambda_4) = (5, 3, 5, 3)`

## Why we are doing this
The lambda terms control how strongly ADMM penalizes:

- `lambda_1`: doorway overflow
- `lambda_2`: safe-threshold violation
- `lambda_3`: physical-capacity violation
- `lambda_4`: spillback

Goal:
- check whether stronger penalties change the ADMM solution
- see whether stronger penalties improve freeway performance or only increase weighted costs

---

## Baseline (same physical state, but weighted penalties change)

| Metric | Set 1 `(1,0.5,1,0.5)` | Set 2 `(2,1,3,1)` | Set 3 `(5,3,5,3)` |
|---|---:|---:|---:|
| Mainline Delay | 26532.175 | 26532.175 | 26532.175 |
| Local Delay | 15101.550 | 15101.550 | 15101.550 |
| Fairness Penalty | 57.361 | 57.361 | 57.361 |
| Doorway Penalty | 5090.232 | 10180.463 | 25451.158 |
| Safe Penalty | 265407.689 | 530815.377 | 1592446.132 |
| Physical Penalty | 0.000 | 0.000 | 0.000 |
| Spillback Penalty | 2852.625 | 5705.250 | 17115.750 |
| Total Capacity Penalty | 273350.545 | 546701.090 | 1635013.040 |

---

## Results Table

| Penalty Set | Mainline Delay (After) | Local Delay (After) | Fairness (After) | Doorway Penalty (After) | Safe Penalty (After) | Spillback Penalty (After) | Total Capacity Penalty (After) | Normalized Weighted Objective (After) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `(1, 0.5, 1, 0.5)` | 15046.948 | 15406.420 | 44.459 | 2496.959 | 0.000 | 4219.089 | 6716.048 | 11.512 |
| `(2, 1, 3, 1)` | 14872.086 | 15420.617 | 43.606 | 4898.970 | 0.000 | 8450.879 | 13349.849 | 12.633 |
| `(5, 3, 5, 3)` | 14438.240 | 15458.962 | 41.372 | 11709.354 | 0.000 | 25445.078 | 37154.432 | 16.716 |

---

## Main observations
- As lambdas increase:
  - **mainline delay improves slightly**
  - **local delay gets slightly worse**
  - **fairness improves slightly**
- Safe-threshold penalty is already driven to `0` in all tested sets
- Physical-capacity penalty remains `0` in all tested sets

## Important note
Doorway and spillback penalties are **weighted penalties**, so larger lambdas automatically make those printed values larger.

So across lambda sets, the most meaningful comparison is:

- mainline delay
- local delay
- fairness
- whether safe penalty is zero
- normalized weighted total objective

## Interpretation
These results suggest:
- stronger lambda values make ADMM a bit more freeway-protective
- but the improvement is moderate
- once safe penalty is already zero, increasing lambdas more does not help much
- `lambda_3` still does nothing in this scenario because physical capacity never activates

## Recommended choice
Best set from the tested values:

- `(lambda_1, lambda_2, lambda_3, lambda_4) = (1, 0.5, 1, 0.5)`

Reason:
- lowest normalized weighted total objective
- safe penalty already eliminated
- stronger lambda sets do not give enough extra benefit to justify larger weighted cost

## Final conclusion
In the current model, changing lambdas affects the ADMM solution only moderately. Stronger lambdas slightly improve freeway-side performance and fairness, but also increase local-side cost and produce a worse normalized weighted objective. Among the tested sets, the smallest penalty set performed best overall.