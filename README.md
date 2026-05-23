# Highway Corridor Delay Optimization with CTM and ADMM

This project models and optimizes traffic delay on **I-405 southbound** using **Caltrans PeMS** data, an **8-cell Cell Transmission Model (CTM)**, and a **dynamic ADMM-based ramp metering framework**.

The main goal is to reduce total corridor cost by combining:

- **mainline delay**
- **local ramp delay**
- **fairness across ramps**
- **capacity protection**

---

## Current main result

Under the **current selected setup**, the ADMM-controlled simulation reduced:

- **mainline delay** from **26532.175** to **15046.948 veh-min**
- **safe-threshold penalty** from **265407.689** to **0.0**

while the **physical-capacity penalty remained inactive**.

This indicates that the ADMM controller substantially improved freeway operating conditions without exceeding hard physical storage limits.

> **Note:** The numerical results below correspond to the current selected setup. They may change if penalty multipliers, ramp-demand assumptions, metering limits, or other model parameters are changed.

---

## Project objective

The corridor objective is defined as:

$$
\mathcal{L}(t)=L_{\text{mainline}}(t)+L_{\text{local}}(t)+L_{\text{fair}}(t)+L_{\text{cap}}(t)
$$

where:

- $L_{\text{mainline}}(t)$ = state-based freeway mainline delay
- $L_{\text{local}}(t)$ = local road / on-ramp delay
- $L_{\text{fair}}(t)$ = fairness penalty across ramps
- $L_{\text{cap}}(t)$ = capacity penalty on the mainline and ramps

---

## Corridor and dataset

**Source:** Caltrans PeMS  
**Facility:** I-405 Southbound  
**Postmile range:** 8.17 to 13.07  
**Corridor length:** 4.90 miles  
**Observed study period:** 2026-01-08, 08:00–09:00  
**Original data interval:** 5 minutes

### Selected mainline stations

| Variable | station_id | location | Abs PM |
|---|---:|---|---:|
| $Q_{in}$ | 1201419 | RED HILL | 8.17 |
| $M_1$ | 1201469 | BRISTOL 1 | 9.31 |
| $M_2$ | 1201497 | FAIRVIEW | 10.05 |
| $M_3$ | 1201525 | HARBOR 1 | 10.97 |
| $M_4$ | 1201558 | HARBOR 2 | 11.27 |
| $M_5$ | 1201589 | EUCLID | 12.27 |
| $Q_{out}$ | 1201620 | TALBERT | 13.07 |

### Selected on-ramps

| Variable | station_id | location | Abs PM |
|---|---:|---|---:|
| $u_1$ | 1201460 | BRISTOL 1 | 9.31 |
| $u_2$ | 1201490 | FAIRVIEW | 10.07 |
| $u_3$ | 1201517 | HARBOR 1 | 10.97 |
| $u_4$ | 1201548 | HARBOR 2 | 11.27 |
| $u_5$ | 1201580 | EUCLID | 12.27 |

## ramp_figure folder
The ramp-location figures were captured using Google Earth. Ramp lengths were also measured in Google Earth and used as supporting geometric reference values for the selected on-ramp locations.

### Selected off-ramps

| Variable | station_id | location | Abs PM |
|---|---:|---|---:|
| $f_1$ | 1201465 | BRISTOL 1 | 9.31 |
| $f_2$ | 1201554 | HARBOR 2 | 11.27 |
| $f_3$ | 1201585 | EUCLID | 12.27 |

---

## Main modeling idea

This project uses two levels of modeling.

### 1. Flow-based benchmark
Observed PeMS speeds and flows are used to compute an empirical **flow-based mainline delay benchmark**.

### 2. State-based optimization model
The actual optimization uses a **state-based mainline delay** that accounts for:

- stored vehicles inside each cell
- blocked discharge
- conservation of vehicles
- ramp inflows and off-ramp outflows

This makes it better suited for control and optimization than a pure flow-based metric.

---

## CTM redesign

The original CTM prototype used **6 cells** and **5-minute steps**, but that discretization was too coarse and risked violating the **CFL condition**.

The model has therefore been redesigned to use:

- **8 CTM cells**
- **30-second simulation step**

The CFL condition is:

$$
\frac{v_{ff}\Delta T}{\Delta x}\le 1
$$

Using corridor median overnight free-flow speed:

$$
v_{ff}=68.1 \text{ mph}
$$

and:

$$
\Delta x=\frac{4.90}{8}=0.6125 \text{ miles}, \qquad \Delta T=30\text{ sec}
$$

gives:

$$
\frac{68.1 \times (1/120)}{0.6125}=0.927 \le 1
$$

So the redesigned CTM grid is physically valid for the selected discretization.

---

## 8-cell CTM network

| Cell | Abs PM Range | On-ramp(s) | Off-ramp(s) |
|---|---|---|---|
| 1 | 8.1700 – 8.7825 | none | none |
| 2 | 8.7825 – 9.3950 | $u_1$ BRISTOL 1 | $f_1$ BRISTOL 1 |
| 3 | 9.3950 – 10.0075 | none | none |
| 4 | 10.0075 – 10.6200 | $u_2$ FAIRVIEW | none |
| 5 | 10.6200 – 11.2325 | $u_3$ HARBOR 1 | none |
| 6 | 11.2325 – 11.8450 | $u_4$ HARBOR 2 | $f_2$ HARBOR 2 |
| 7 | 11.8450 – 12.4575 | $u_5$ EUCLID | $f_3$ EUCLID |
| 8 | 12.4575 – 13.0700 | none | none |

### Lane-count assumption

- Cell 5 has **6 lanes**
- All other cells have **5 lanes**

### Per-cell capacities

Using average per-lane doorway capacity:

$$
35 \text{ veh/min/ln}
$$

and jam density:

$$
k_j = 193 \text{ veh/mi/ln}
$$

the current 8-cell capacities are:

| Cell | Lanes | Doorway capacity $C_i$ | Physical capacity $N_{max,i}$ |
|---|---:|---:|---:|
| 1 | 5 | 87.5 | 591.062 |
| 2 | 5 | 87.5 | 591.062 |
| 3 | 5 | 87.5 | 591.062 |
| 4 | 5 | 87.5 | 591.062 |
| 5 | 6 | 105.0 | 709.275 |
| 6 | 5 | 87.5 | 591.062 |
| 7 | 5 | 87.5 | 591.062 |
| 8 | 5 | 87.5 | 591.062 |

---

## Delay model components

### Mainline delay
State-based freeway delay uses cell occupancy and discharged flow relative to free-flow travel time.

### Local delay
Ramp delay is modeled from queue evolution:

$$
R_{i,t}=R_{i,t-1}+a_{i,t}-u_{i,t}
$$

### Fairness
Ramp stress is normalized by ramp storage capacity:

$$
\phi_{i,t}^{cap}=\min\left(\frac{R_{i,t}}{R_{max,i}},1\right)
$$

and fairness penalizes imbalance across ramps.

### Capacity protection
Capacity protection includes:

- doorway flow limit
- safe occupancy threshold
- hard physical storage limit
- spillback beyond ramp storage

---

## Baseline and controlled simulations

The project now includes both:

- a **120-step uncontrolled baseline CTM simulation**
- a **120-step ADMM-controlled simulation**

Since each step is 30 seconds, the total horizon is:

- **120 steps**
- **60 minutes**

The baseline simulation tracks:

- freeway state evolution
- ramp queues
- spillback
- mainline delay
- local delay
- fairness penalty
- doorway penalty
- safe-threshold penalty
- physical-capacity penalty
- total capacity penalty
- total objective

The ADMM-controlled simulation uses the same physical CTM, but replaces fixed observed ramp release with optimized ramp release decisions at each time step.

---

## Objective normalization

The raw objective terms operate on very different scales. For example:

- delay terms may be on the order of tens of thousands
- safe-threshold penalties may be on the order of hundreds of thousands or millions

To avoid domination by the largest raw term, the project computes baseline normalization constants from the uncontrolled 120-step simulation and uses a normalized weighted objective of the form:

$$
J =
\alpha_{main}\tilde D_{main}
+ \beta_{local}\tilde D_{local}
+ \gamma \tilde L_{fair}
+ \lambda_1 \tilde P_{door}
+ \lambda_2 \tilde P_{safe}
+ \lambda_3 \tilde P_{phys}
+ \lambda_4 \tilde P_{spill}
$$

This allows the optimizer to compare terms fairly while still enforcing modeling priorities through the weights.

---

## ADMM framework

The ADMM controller optimizes ramp release decisions at ramps:

- $u_1$ to $u_5$

The optimization is split into two coupled blocks:

### Ramp block
Optimizes:

- local delay
- fairness penalty
- spillback penalty

### Freeway block
Optimizes:

- mainline delay
- doorway penalty
- safe-threshold penalty
- physical-capacity penalty

ADMM coordinates the two blocks by:

- solving a local update for ramp-side variable copy $u$
- solving a global update for freeway-side variable copy $z$
- updating the dual variable $y$
- checking primal and dual residuals for convergence

This allows ramp decisions to be optimized while maintaining consistency between the ramp subsystem and the freeway CTM subsystem.

---

## Final selected setup used in reported results

The main baseline-vs-ADMM comparison uses the following parameter set:

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
- `initial ramp queue = 0`

---

## Baseline vs ADMM (current selected setup)

| Metric | Baseline | ADMM |
|---|---:|---:|
| Mainline Delay (veh-min) | 26532.175 | 15046.948 |
| Local Delay (veh-min) | 15101.550 | 15406.420 |
| Fairness Penalty | 57.361 | 44.459 |
| Doorway Penalty | 5090.232 | 2496.959 |
| Safe Penalty | 265407.689 | 0.000 |
| Spillback Penalty | 2852.625 | 4219.089 |
| Normalized Weighted Total Objective | 17.000 | 11.512 |

### Interpretation of the reported setup

In the final selected setup:

- **mainline delay, local delay, fairness, doorway, safe-threshold, and spillback terms were all active**
- **physical-capacity penalty remained inactive**

This means the corridor became operationally congested and exceeded the safe operating threshold in the uncontrolled baseline, but never reached hard jam-density storage.

The ADMM controller improved freeway performance substantially, primarily by reducing ramp releases relative to the observed baseline, which eliminated safe-threshold violations and lowered mainline delay at the cost of modestly higher local delay and spillback.

---

## Sensitivity analysis

The project also includes sensitivity studies on key parameters, including:

- `meter_capacity`
- `alpha_main`
- `beta_local`
- `gamma`
- `eta`
- `lambda_1, lambda_2, lambda_3, lambda_4`
- `arrival_multiplier`
- initial ramp queue

These tests show that:

- `meter_capacity` produces the strongest change in ADMM behavior
- `gamma` has a moderate effect
- `eta` mainly changes when the safe-threshold penalty activates
- `alpha_main` and `beta_local` have relatively small effects in the tested ranges
- physical-capacity penalty remains inactive in the reported final scenarios

Among the tested parameters, **`meter_capacity` produced the strongest change in ADMM behavior**.

---

## Current project status

### Completed
- corridor and station selection
- flow-based benchmark delay calculations
- state-based delay formulation
- local ramp delay model
- fairness penalty model
- capacity penalty model
- 8-cell, 30-second CTM redesign
- initial mainline state reconstruction
- ramp initial state and demand setup
- one-step CTM update module
- 120-step baseline CTM simulation
- objective normalization
- one-step ADMM optimization
- 120-step ADMM-controlled simulation
- baseline vs ADMM comparison
- sensitivity analysis on key parameters

### Future extensions
- time-varying boundary inflow
- time-varying ramp demand
- alternative fairness definitions
- calibration against additional observed periods
- comparison across multiple congestion scenarios

---

## Sensitivity notes

Detailed sensitivity-analysis notes are available in `sensitivity/`:

- ramp metering sensitivity
- alpha/beta weight sensitivity
- fairness weight sensitivity
- safe-threshold sensitivity
- penalty-weight sensitivity
- arrival-demand sensitivity
- initial ramp queue sensitivity
---



## Repository purpose

This repository documents the transition from:

- coarse static segment analysis

to

- fine dynamic CTM baseline simulation

and finally to

- dynamic ADMM-controlled ramp metering on the same 8-cell freeway corridor

The overall purpose is to create a physically consistent and optimization-ready freeway corridor model that can support delay reduction, ramp metering, and future control experiments.
