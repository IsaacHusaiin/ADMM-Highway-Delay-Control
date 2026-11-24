# Freeway Ramp-Metering Project — Overview

## 1. Project Goal

This project builds a traffic-control simulation for a short freeway corridor using a 9-cell Cell Transmission
Model (CTM), driven by Caltrans PeMS District 5 data. It compares fully open ramps, fixed-rate metering, and
receding-horizon control.

The evaluation tracks mainline time spent, ramp waiting, upstream and external-entry queues, fairness,
safety-threshold exposure, and spillback beyond ramp storage.

> Can an optimized ramp-metering controller improve the total system objective compared with fully open
> ramps and a fixed-rate policy?

---

## 2. Main Files

### Raw data inputs, PeMS District 5

- **`d05_text_meta_2026_04_28.txt`** — PeMS station metadata with detector IDs, freeway, direction, postmile,
  station type, and lane count. The benchmark uses it to identify the corridor's stations.
- **`d05_text_station_5min_2026_05_27.txt`** — Timestamped PeMS flow, occupancy, and speed measurements.
  The benchmark converts the five-minute measurements into 15-second CTM inputs.

### `Benchmark_calculation.ipynb`

The benchmark notebook builds the 9-cell CTM from the raw PeMS files, simulates fully open ramps, and verifies
vehicle conservation and flow limits. It exports `shared_benchmark_inputs.pkl` and reports a two-hour baseline
objective of **88,338.75**.

### `Benchmark_calculation.py`

The standalone script executes the benchmark notebook's model setup and simulation in memory, using the same
PeMS files. It checks the two-hour totals and scores the zero-demand clearance period. The combined baseline
objective is **97,342.00**. The script runs from Python with NumPy and pandas, without a Jupyter session or a
cached pickle.

### `fixed_policy.ipynb`

The fixed-policy notebook searches for one constant release cap per ramp. It evaluates candidate caps through
the exact CTM using the two-hour objective. The resulting policy provides the fixed-rate comparison baseline.

### `Benchmark_convex_QP.ipynb`

The full-horizon sequential QP constructs local convex approximations of the exact CTM. It replays trial
commands through the exact model and accepts a step when the replay improves the objective. Its local QP
objective is a planning diagnostic.

### `ADMM_MPC.ipynb`

The MPC notebook solves a short-horizon QP at each 15-second step, applies the first ramp command, and replans
from the resulting exact CTM state. It runs the same planning model with Clarabel and OSQP, whose solver uses
ADMM. Its final comparison uses exact replay and clearance.

### `shared_benchmark_inputs.pkl`

This generated export contains simulation settings, initial states, demand series, road capacities, ramp
metadata, objective weights, benchmark results, and normalization scales. The current notebooks and standalone
script use the benchmark notebook as the source of the CTM and inputs.

---

## 3. Shared Input Design

The benchmark notebook keeps the following inputs consistent across experiments.

- Mainline initial inventory and initial ramp, spillback, and external-entry queues
- Ramp arrivals and observed ramp flows
- Upstream boundary demand, external inflows, and local exit flows
- Sending, receiving, safe-threshold, and physical storage capacities
- Ramp storage limits and free-flow travel times
- Objective weights and official benchmark totals

Ramp arrivals are fixed external demand. Changing the meter command changes how many vehicles are released and
how many remain queued. Demand is supplied separately.

---

## 4. Corridor Setup

The simulation covers 16:00–18:00 on May 27, 2026. The corridor has nine mainline cells and four controlled
on-ramps. The two-hour window uses 480 steps of 15 seconds each. Cell 9 has a capacity of 2,400 vehicles per hour.

```text
Δt = 15 seconds = 0.25 minutes

4th    → Cell 2
Price  → Cell 2
Mattie → Cell 6
Avila  → Cell 9
```

Avila uses a priority merge into Cell 9 with priority `π = 0.3` when ramp flow and Cell 8 mainline flow compete
for receiving capacity.

---

## 5. CTM Modeling Setup

The CTM tracks vehicle inventory in each cell. At each step, actual flow is limited by upstream sending capacity
and downstream receiving capacity. Local exit flows share the cell's sending budget. Uncontrolled external
arrivals use receiving capacity first and wait in an external-entry queue if they cannot enter. Controlled ramp
releases follow the receiving and merge rules. Cell 9 discharges traffic out of the modeled corridor.

---

## 6. Ramp Queue Setup

Each ramp has a physical queue `R` and spillback `B` beyond its storage limit. The accepted release is the flow
that enters the mainline after demand and receiving constraints are applied.

```text
waiting demand next step = R + B + new ramp arrivals − accepted ramp release
R = waiting demand up to the ramp storage limit
B = waiting demand beyond the ramp storage limit
```

---

## 7. Main Assumptions

### 1. Ramp arrivals are estimated

PeMS ramp detectors measure discharge flow. The benchmark estimates ramp demand from that flow using an
arrival multiplier of `1.2`.

```text
ramp arrivals = arrival multiplier × observed ramp flow
```

### 2. Ramp arrivals are external demand

The arrival series stays fixed across policies. Available ramp demand includes vehicles already waiting in the
physical and spillback queues.

### 3. Mainline scoring uses time spent

Mainline time spent is the average number of vehicles in each cell during the step, multiplied by the step
duration. The benchmark records a free-flow-adjusted delay proxy as a diagnostic.

### 4. Safe capacity and physical capacity are different

The safe threshold is an operational occupancy threshold. Exposure above it contributes to the objective.
Physical capacity is a hard storage limit enforced by the exact CTM.

### 5. Spillback is penalized separately and linearly

The spillback exposure is the average overflow queue multiplied by the step duration. The objective weights
this exposure by `λ_spillback`.

### 6. All models use the same benchmark inputs

The experiments reuse the benchmark's demand, capacities, and initial states. Realized scores use the same
evaluation weights. The mainline-focused experiment changes the planning weight.

---

## 8. Objective Function Setup

```text
raw objective =
    AW × mainline time spent
  + ramp waiting time
  + upstream boundary waiting time
  + external-entry waiting time
  + fairness penalty
  + λ_safe × safety-threshold exposure
  + λ_spillback × spillback exposure
```

The objective terms are measured in vehicle-minutes after applying their weights. The benchmark uses
`AW = 1`, `γ = 1`, `λ_safe = 0.5`, and `λ_spillback = 0.5`.

- **Waiting time** uses step-average queues. Ramp waiting includes both `R` and `B`.
- **Fairness** uses the unclipped ramp stress `φ_r = step-average(R_r + B_r) / Rmax_r`. Each step adds
  `γ × Δt × mean(Rmax) × Σ(φ_r − mean(φ))²`.
- **Safety exposure** uses the positive excess of step-average occupancy over the safe threshold, summed
  across cells and multiplied by `Δt`.
- **Spillback exposure** uses step-average `B`, summed across ramps and multiplied by `Δt`.

---

## 9. Normalization Setup

The benchmark export includes fixed normalization scales. The current comparisons use the weighted raw
objective in vehicle-minutes.

---

## 10. Controller and Optimization Setup

### Benchmark

The benchmark sets each ramp command high enough to request all available ramp demand. The exact CTM still
limits actual release by receiving capacity and merge rules.

### Fixed Policy

A constant command cap is applied at each ramp throughout the two-hour window. The search selected these caps
in vehicles per 15 seconds.

```text
4th    = 11.253104
Price  = 14.769074
Mattie =  3.060000
Avila  =  2.219721
```

### Centralized Convex QP

The full-horizon search solves a sequence of QPs with locally linearized dynamics. The last local model
predicted a cost of **88,328.03**. No trial improved the exact CTM replay, so the search retained the fully open
policy with its **88,338.75** two-hour cost.

### ADMM-MPC

The standard controller uses `K = 5` and `K = 10` steps with the benchmark's mainline weight `AW = 1`. The QP
adds a 30-minute terminal cost on ramp, boundary, and external-entry queues. At every step, the controller
solves the window, applies the first command through the exact CTM, and replans from the measured state.

---

## 11. How the Files Work Together

Keep the notebooks, script, and both PeMS files in the same folder. The notebook dependencies are listed in
`README.md`.

```text
1. Benchmark_calculation.ipynb
   → builds and validates the fully open CTM replay from the raw data
   → exports shared_benchmark_inputs.pkl

2. Benchmark_calculation.py
   → uses the benchmark notebook and raw files in memory
   → prints the two-hour and clearance-adjusted baseline

3. fixed_policy.ipynb
   → runs the benchmark notebook and searches for fixed release caps

4. Benchmark_convex_QP.ipynb
   → runs the benchmark notebook and tests full-horizon QP candidates in the exact CTM

5. ADMM_MPC.ipynb
   → builds the benchmark setup in memory and runs both MPC horizons with Clarabel and OSQP
   → scores the exact replay through clearance

6. ADMM_MPC_mainlinedelay_focus.ipynb
   → runs the separate mainline-priority experiment on the same benchmark
```

Run the standalone check from PowerShell in the project folder.

```powershell
python .\Benchmark_calculation.py
```

---

## 12. Final Result Summary

The comparison adds a clearance period after the two-hour window. New demand stops and the ramps open fully
until the remaining traffic clears. Ramp service and backlog are recorded at the two-hour cutoff.

| Policy | Objective after clearance | Change vs. fully open |
| --- | ---: | ---: |
| Fully open benchmark | 97,342.00 | 0.000% |
| Best fixed rate found | **97,322.95** | **−0.020%** |
| Full-horizon QP replay | 97,342.00 | 0.000% |
| MPC, K = 5, Clarabel and OSQP | 97,404.90–97,404.95 | +0.065% |
| MPC, K = 10, Clarabel and OSQP | 97,475.27–97,475.37 | +0.137% |

The fully open and fixed-rate results match the July 12 report at its displayed precision. The K = 5 cost
rounds to the report's **97,405**, with different component costs and ramp backlog. The reconstructed K = 10
planner scores about **154 vehicle-minutes lower** than the report's **97,629**.

---

## 13. Important Reporting Note

The fixed-rate policy achieved the lowest total cost in the rerun. Both standard MPC horizons reduced freeway
time and increased ramp waiting and fairness costs. Both had higher combined costs than fully open ramps.

The separate mainline-priority experiment uses `K = 5`, `AW = 2.3`, and a command cap based on observed ramp
flow times the arrival multiplier. Its Clarabel run reduced freeway time by about **1,132 vehicle-minutes** and
increased combined cost by **2.37%** to **99,652.31**. About **62 vehicles** remained on the ramps at two hours.

---

## 14. Convex QP and ADMM Interpretation

The QP provides the planner's forecast. Clarabel and OSQP solve the same convex planning model, with OSQP using
ADMM. Solver status and constraint residuals describe the planning problem. The exact CTM replay determines
the realized traffic flows, queue outcomes, and policy score.
