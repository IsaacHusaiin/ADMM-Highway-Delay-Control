# Fairness Weight Sensitivity: `gamma`

## Purpose

This sensitivity test studies how the fairness weight `gamma` affects the ramp-metering controller.

The fairness weight controls how strongly the controller penalizes imbalance between ramp queues.

A larger `gamma` gives more importance to keeping ramp queue stress balanced across ramps.

---

## Fairness Term

Ramp queue stress is computed by comparing each ramp queue to its maximum storage capacity.

For ramp \(i\):

$$
\phi_{i,t}^{cap}
=
\min
\left(
\frac{R_{i,t}}{R_{max,i}},
1
\right)
$$

where:

$$
R_{i,t}
$$

is the ramp queue at ramp \(i\) and time \(t\), and

$$
R_{max,i}
$$

is the maximum storage capacity of ramp \(i\).

The fairness penalty compares queue stress across ramps:

$$
P_{\text{fair},t}
=
\gamma
\sum_{i<j}
\left(
\phi_{i,t}^{cap}
-
\phi_{j,t}^{cap}
\right)^2
$$

---

## Meaning of `gamma`

The parameter `gamma` controls the importance of fairness in the objective.

If `gamma` is small, the controller gives less importance to balancing ramp queues.

If `gamma` is large, the controller gives more importance to avoiding large differences between ramp queue stress levels.

In simple terms:

```text
small gamma = fairness matters less
large gamma = fairness matters more