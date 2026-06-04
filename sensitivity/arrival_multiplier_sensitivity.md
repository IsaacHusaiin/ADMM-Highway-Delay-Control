# Ramp Arrival Sensitivity

## Purpose

This section tests how changing ramp arrival pressure affects the CTM and controller behavior.

The ramp arrival multiplier controls how much demand enters the on-ramp queues relative to the observed ramp-release series.

The basic idea is:

$$
a_{i,t}
=
m
\cdot
u_{i,t}^{observed}
$$

where:

$$
a_{i,t}
$$

is the ramp arrival at ramp \(i\) and time \(t\),

$$
m
$$

is the ramp arrival multiplier, and

$$
u_{i,t}^{observed}
$$

is the observed ramp release.

A larger multiplier means more vehicles arrive at the ramps.

---

## Why This Matters

Ramp arrival pressure affects the local/ramp side of the system.

When ramp demand increases, the controller may need to hold more vehicles at ramps to protect the freeway mainline. This can increase:

- ramp queue length
- local ramp delay
- spillback
- queue stress

The sensitivity test helps show whether the model response is mainly driven by freeway congestion, ramp demand pressure, or ramp storage limits.

---

## Expected Behavior

When the ramp arrival multiplier increases:

- ramp queues usually increase
- local delay usually increases
- spillback risk usually increases
- fairness may change depending on whether all ramps become similarly stressed
- mainline conditions may stay protected if the controller restricts ramp release
- freeway delay may increase if too much ramp demand is released into the mainline

---

## Fairness Interpretation

A lower fairness penalty does not always mean the system is healthier.

The fairness term measures imbalance across ramp queue stress levels.

If all ramps become similarly congested, the fairness penalty can decrease even though the ramp system is under heavier pressure.

So fairness must be interpreted together with:

- local delay
- spillback
- ramp queue size
- served demand
- final ramp queue

---

## Main Interpretation

This sensitivity test shows how ramp demand pressure shifts the burden between the freeway and the ramps.

A well-behaved controller should:

- avoid excessive mainline congestion
- avoid unsafe cell occupancies
- limit spillback when possible
- keep ramp queues physically meaningful
- balance freeway protection against ramp delay

---

## What to Report

For each tested ramp arrival multiplier, report:

- mainline delay
- local ramp delay
- fairness penalty
- doorway penalty
- safe-threshold penalty
- physical-capacity penalty
- spillback penalty
- total system delay
- normalized weighted objective
- final ramp queues
- total served ramp demand
- total spilled demand

---

## Final Takeaway

Ramp arrival sensitivity is important because it tests whether the controller remains stable under different ramp-demand levels.

The key question is not only whether the normalized objective improves, but also whether the controller is protecting the freeway by creating unacceptable ramp queues or spillback.

This sensitivity test should therefore be interpreted together with demand accounting.