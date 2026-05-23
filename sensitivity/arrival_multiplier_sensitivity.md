## What this is
We tested how changing the **ramp demand pressure** affects ADMM, while keeping:

- `meter_capacity = 0.9 * observed_release`
- `alpha_main = 10`
- `beta_local = 3`
- `gamma = 2`
- `eta = 0.7`
- `(lambda_1, lambda_2, lambda_3, lambda_4) = (1, 0.5, 1, 0.5)`

Tested values:

- `arrival_multiplier ∈ {1.2, 1.5, 1.8, 2.0, 5.0}`

## Why we are doing this
`arrival_multiplier` controls how many cars arrive to the ramps relative to observed release.

Example:

$$
a_t = \text{arrival_multiplier} \cdot u_{obs}
$$

So:
- larger `arrival_multiplier` = heavier ramp demand
- smaller `arrival_multiplier` = lighter ramp demand

Goal:
- see how increasing ramp demand changes freeway performance, local delay, fairness, and spillback
- check whether ADMM can still protect the freeway under higher ramp pressure

---

## Baseline (same freeway state, but ramp-side terms change with arrival pressure)

| Metric | 1.2 | 1.5 | 1.8 | 2.0 | 5.0 |
|---|---:|---:|---:|---:|---:|
| Mainline Delay | 26532.175 | 26532.175 | 26532.175 | 26532.175 | 26532.175 |
| Local Delay | 12735.570 | 15101.550 | 15693.000 | 15889.550 | 16478.600 |
| Fairness Penalty | 143.559 | 57.361 | 35.948 | 28.621 | 7.578 |
| Doorway Penalty | 5090.232 | 5090.232 | 5090.232 | 5090.232 | 5090.232 |
| Safe Penalty | 265407.689 | 265407.689 | 265407.689 | 265407.689 | 265407.689 |
| Spillback Penalty | 356.675 | 2852.625 | 7705.589 | 12242.430 | 205987.560 |
| Total Capacity Penalty | 270854.595 | 273350.545 | 278203.509 | 282740.350 | 476485.480 |

---

## Results Table

| `arrival_multiplier` | Mainline Delay (After) | Local Delay (After) | Fairness Penalty (After) | Doorway Penalty (After) | Safe Penalty (After) | Spillback Penalty (After) | Total Capacity Penalty (After) | Normalized Weighted Objective (After) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.2 | 14675.125 | 14214.341 | 84.542 | 2399.143 | 0.000 | 941.487 | 3340.630 | 11.848 |
| 1.5 | 15046.948 | 15406.420 | 44.459 | 2496.959 | 0.000 | 4219.089 | 6716.048 | 11.512 |
| 1.8 | 15189.999 | 15821.188 | 30.224 | 2527.750 | 0.000 | 9852.709 | 12380.459 | 11.567 |
| 2.0 | 15229.150 | 15975.431 | 25.372 | 2534.017 | 0.000 | 14936.110 | 17470.127 | 11.637 |
| 5.0 | 15417.685 | 16484.152 | 7.152 | 2571.916 | 0.000 | 216489.289 | 219061.204 | 11.730 |

---

## Main observations
- Increasing `arrival_multiplier` increases **ramp demand pressure**
- As demand increases:
  - **local delay increases**
  - **spillback penalty increases sharply**
- ADMM still keeps:
  - **safe penalty = 0**
  - **mainline delay relatively stable**
- Mainline delay after ADMM only worsens moderately as arrival pressure increases

## Important note
The fairness penalty decreases as `arrival_multiplier` increases, but this does **not necessarily mean the system is healthier**.

Reason:
- when all ramps are pushed toward similar high stress / near-full conditions, the fairness-difference term can shrink
- so lower fairness penalty here may simply mean ramps are becoming similarly overloaded

## Interpretation
This test shows that `arrival_multiplier` mainly changes the **ramp-side burden**, especially spillback.

So:
- `arrival_multiplier` is important for ramp/local-road stress
- but it does not strongly change the freeway-side ADMM solution under the current setup

## Recommended range
A reasonable practical range is:

- `1.5` (we chose this)
- `1.8`
- `2.0`

These create meaningful ramp pressure without becoming extreme.

## Extreme stress test
`arrival_multiplier = 5.0` is not a normal operating case.  
It is best treated as a **stress-test scenario**.

## Final conclusion
In the current model, increasing `arrival_multiplier` mainly increases local delay and spillback, while ADMM still keeps safe-threshold violations at zero and maintains similar freeway-side performance. This means ramp demand pressure affects the local/ramp side much more strongly than the freeway side under the current controller settings.