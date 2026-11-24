# ADMM-MPC Ramp Metering with a 9-Cell CTM

This project studies freeway ramp metering using a 9-cell Cell Transmission Model (CTM), Caltrans PeMS District 5 data, a fixed-policy baseline, a centralized convex QP surrogate, and an ADMM-MPC controller.

The goal is to test whether an optimized controller can reduce the total system objective compared with fully open ramps and simple fixed metering policies.

---

## Main idea

| File | Purpose |
| --- | --- |
| `Benchmark_calculation.ipynb` | Builds and validates the fully open CTM benchmark and exports shared inputs. |
| `Benchmark_calculation.py` | Runs the benchmark outside Jupyter and reports its two-hour and clearance-adjusted scores. |
| `fixed_policy.ipynb` | Searches for one constant release cap per ramp. |
| `Benchmark_convex_QP.ipynb` | Tests full-horizon sequential QP candidates through the exact CTM. |
| `ADMM_MPC.ipynb` | Runs the standard receding-horizon controller. |
| `ADMM_MPC_mainlinedelay_focus.ipynb` | Runs the separate mainline-weighted controller experiment. |

`Benchmark_calculation.ipynb` exports `shared_benchmark_inputs.pkl`. The notebooks and standalone script use the benchmark notebook as the source for the CTM and inputs.

---

## Data

Raw PeMS inputs:

```text
d05_text_meta_2026_04_28.txt
d05_text_station_5min_2026_05_27.txt
```

The benchmark notebook converts the 5-minute PeMS detector data into 15-second CTM inputs.

---

## CTM setup

Final model setup:

| Item               |         Value |
| ------------------ | ------------: |
| Mainline cells     |             9 |
| Controlled ramps   |             4 |
| Time step          |    15 seconds |
| Horizon            |     480 steps |
| Window             |       2 hours |
| Arrival multiplier |           1.2 |
| Cell 9 capacity    | 2400 veh/hour |
| Spillback penalty  |        Linear |

Ramp-to-cell mapping:

```text
4th    → Cell 2
Price  → Cell 2
Mattie → Cell 6
Avila  → Cell 9
```

Avila uses a priority merge into Cell 9 with priority:

```text
π = 0.3
```

---

## Objective

The raw objective is:

```text
mainline time spent
+ ramp waiting time
+ upstream boundary waiting time
+ external-entry waiting time
+ fairness penalty
+ weighted safety-threshold exposure
+ weighted spillback exposure
```

Fairness penalizes differences in normalized queue stress across ramps. Queue stress includes the physical queue `R` and spillback `B`.

```text
φ = step-average (R + B) / Rmax
```

The spillback penalty is linear in the average overflow queue.

```text
spillback penalty per ramp per step = λ_spillback × step-average B × Δt
```

---

## Model roles

### Benchmark

`Benchmark_calculation.ipynb` runs the exact CTM with all ramps fully open.

The notebook reports the two-hour objective. `Benchmark_calculation.py` also reports the clearance-adjusted objective.

```text
Two-hour objective = 88,338.75
Objective after clearance = 97,342.00
```

---

### Fixed policy

`fixed_policy.ipynb` searches for one constant release cap per ramp using the two-hour objective.

Best caps found, in vehicles per 15 seconds

```text
4th    = 11.253104
Price  = 14.769074
Mattie =  3.060000
Avila  =  2.219721

Two-hour objective = 88,319.70
Objective after clearance = 97,322.95
```

This is the fixed-rate comparison baseline.

---

### Convex QP

`Benchmark_convex_QP.ipynb` builds a convex surrogate of the exact CTM control problem.

The exact CTM has nonconvex pieces such as min/max flow rules, merge switching, and queue/spillback splitting. The sequential QP uses locally linearized dynamics, capacity constraints, and slack variables.

The last local QP predicted an objective of **88,328.03**. No trial improved the exact CTM replay, so the full-horizon search kept the fully open policy at **88,338.75** over two hours.

---

### ADMM-MPC

`ADMM_MPC.ipynb` runs the standard controller.

At every 15-second step, it:

```text
observes the current exact CTM state
solves a short-horizon convex QP
applies only the first optimized ramp command
updates the exact CTM
replans
```

The tested controller settings were

```text
K = 5 and 10 steps
AW = 1.0
Terminal queue weight = 30 minutes
```

Clarabel and OSQP solve the same planning QP. The OSQP-first runs can fall back to Clarabel.

`ADMM_MPC_mainlinedelay_focus.ipynb` uses `K = 5` and `AW = 2.3` in the planner. It caps meter commands at observed ramp flow times the arrival multiplier and scores realized performance with the common benchmark weights.

---

## Final results

The table shows exact CTM costs at the default arrival multiplier of **1.2**, including clearance with fully open ramps and zero new demand.

| Policy | Cost after clearance | Change vs. fully open |
| --- | ---: | ---: |
| Fully open benchmark | 97,342.00 | 0.000% |
| Best fixed rate found | **97,322.95** | **−0.020%** |
| Full-horizon convex QP replay | 97,342.00 | 0.000% |
| Standard MPC, K = 5 | 97,404.90–97,404.95 | +0.065% |
| Standard MPC, K = 10 | 97,475.27–97,475.37 | +0.137% |
| Mainline-focused MPC, K = 5, AW = 2.3 | 99,652.31–99,652.95 | +2.373% to +2.374% |

MPC ranges cover the Clarabel and OSQP-first runs.

---

## How to run

Run notebooks in this order:

```text
1. Benchmark_calculation.ipynb
2. fixed_policy.ipynb
3. Benchmark_convex_QP.ipynb
4. ADMM_MPC.ipynb
5. ADMM_MPC_mainlinedelay_focus.ipynb
```

Keep the notebooks, Python script, and raw PeMS files in the same folder. Run the standalone benchmark from that folder.

```powershell
python .\Benchmark_calculation.py
```

---

## Requirements

```text
numpy
pandas
matplotlib
seaborn
scipy
cvxpy
clarabel
osqp
ipython
nbformat
```

---

## Important note

At the default arrival multiplier of 1.2, the fixed-rate policy had the lowest total objective. The MPC runs reduced freeway time and increased ramp waiting and fairness costs.

The convex QP and ADMM convergence claims apply to the convex surrogate problem. Final performance is always evaluated using the exact CTM replay.
