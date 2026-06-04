# Initial Ramp Queue Sensitivity

## Purpose

This sensitivity test studies how the starting ramp queue affects the CTM and controller behavior.

The initial ramp queue represents the number of vehicles already waiting on each ramp at the beginning of the simulation horizon.

The tested idea is:

$$
R_{i,0}
=
p
\cdot
R_{max,i}
$$

where:

$$
R_{i,0}
$$

is the initial queue at ramp \(i\),

$$
p
$$

is the initial queue percentage, and

$$
R_{max,i}
$$

is the maximum storage capacity of ramp \(i\).

---

## Why This Matters

Ramp metering decisions depend on current ramp queues.

If the ramps already have vehicles waiting at the start of the simulation, the controller has less available storage before spillback occurs.

Higher initial ramp queues can increase:

- local ramp delay
- ramp queue stress
- spillback risk
- fairness pressure

This test checks whether the controller is sensitive to the initial ramp congestion level.

---

## Expected Behavior

When the initial ramp queue increases:

$$
R_{i,0} \uparrow
$$

the ramp side becomes more stressed.

This usually leads to:

```text
higher initial queue
→ higher local delay
→ higher spillback risk
→ less available ramp storage