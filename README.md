# Highway Corridor Delay Optimization with CTM and ADMM

This project models and optimizes traffic delay on **I-405 southbound** using **Caltrans PeMS** data, a **Cell Transmission Model (CTM)**, and a planned **ADMM-based ramp control framework**.

The main goal is to minimize total corridor cost by combining:

- **mainline delay**
- **local ramp delay**
- **fairness across ramps**
- **capacity protection**

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
- $L_{\text{cap}}(t)$ = capacity penalty on the mainline

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

### Selected off-ramps

| Variable | station_id | location | Abs PM |
|---|---:|---|---:|
| $f_1$ | 1201465 | BRISTOL 1 | 9.31 |
| $f_2$ | 1201554 | HARBOR 2 | 11.27 |
| $f_3$ | 1201585 | EUCLID | 12.27 |

---

## Main modeling idea

This project uses two levels of modeling:

### 1. Flow-based benchmark
Observed PeMS speeds and flows are used to compute an empirical **flow-based mainline delay benchmark**.

### 2. State-based optimization model
The actual optimization uses a **state-based mainline delay** that accounts for:

- stored vehicles inside each segment
- blocked discharge
- conservation of vehicles
- ramp inflows and off-ramp outflows

This makes it better suited for control and optimization than a pure flow-based metric.

---

## Current CTM redesign status

The original CTM prototype used **6 cells** and **5-minute steps**, but that discretization was too coarse.

The model has now been redesigned to use:

- **8 CTM cells**
- **30-second simulation step**

This redesign was chosen to satisfy the **CFL condition**:

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

So the new CTM grid is physically valid.

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

- Cell 5: **6 lanes**
- All other cells: **5 lanes**

### Current per-cell capacities

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

### Capacity penalty
Capacity protection includes:

- doorway flow limit
- safe occupancy threshold
- hard physical storage limit

---

## Current progress

### Completed
- corridor and station selection
- flow-based benchmark delay calculations
- state-based delay formulation
- local ramp delay model
- fairness penalty model
- capacity penalty model
- first 6-cell CTM prototype
- corrected CTM flow-propagation logic
- redesigned **8-cell, 30-second CTM network**
- coded **network-definition block**:
  - cell ranges
  - ramp assignment
  - lane counts
  - doorway capacities
  - physical capacities

### In progress
- Block B: initial state definition
  - mainline initial occupancies $x_i^0$
  - ramp initial queues $R_i^0$

### Planned
- one-step CTM update module
- multi-step baseline CTM simulation
- objective evaluation modules
- ADMM ramp-control implementation
- baseline vs controlled comparison

---

