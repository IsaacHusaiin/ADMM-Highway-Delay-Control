# Freeway Ramp-Metering Project — Overview

## 1. Project Goal

This project builds a traffic-control simulation for a short freeway corridor using a 9-cell Cell Transmission
Model (CTM), driven by real Caltrans PeMS District 5 data. The goal is to compare the original field-observed
ramp-release behavior against controlled ramp-metering policies.

The project does not only measure freeway delay. It also tracks ramp queues, local ramp delay, fairness across
ramps, safe-capacity violations, physical-capacity violations, and spillback beyond ramp storage.

The main research question is:

> Can an optimized ramp-metering controller improve the total system objective compared with the historical
> benchmark and a simple fixed-policy baseline?

---

## 2. Main Files

### Raw data inputs, PeMS District 5

- **`d05_text_meta_2026_04_28.txt`** — PeMS station metadata. This file contains each detector station's ID,
  freeway, direction, county, postmile, latitude/longitude, length, station type, lane count, and station name.
  It is used to identify the corridor's mainline stations, on-ramp stations, and off-ramp stations.
- **`d05_text_station_5min_2026_05_27.txt`** — PeMS 5-minute station data. This file contains timestamped flow,
  occupancy, and speed measurements. The benchmark notebook converts these 5-minute measurements into the
  15-second inputs used by the CTM simulation.

### `Benchmark_calculation.ipynb`

This is the source-of-truth benchmark notebook. It reads the PeMS metadata and station-data files, extracts the
selected corridor, builds the 9-cell CTM setup, computes the official historical benchmark, validates the CTM
replay, and exports the shared input file used by the other notebooks.

The benchmark is not a "do-nothing" case. It is the historical observed-command baseline. In other words, it
replays the observed ramp-release behavior from the data and evaluates it through the corrected CTM.

```text
Benchmark_calculation.ipynb = exact CTM benchmark replay + shared input export
```

It exports:

```text
shared_benchmark_inputs.pkl
```

This exported file contains the simulation settings, initial states, time-series inputs, capacities, ramp
metadata, free-flow travel times, objective weights, official benchmark totals, and normalization denominators.

### `Benchmark_calculation.py`

This is the clean standalone validation script for the benchmark simulation. It loads:

```text
shared_benchmark_inputs.pkl
```

Then it reruns the observed-release benchmark with the benchmark engine and verifies that the reproduced totals
match the official benchmark totals.

```text
Benchmark_calculation.py = standalone validation script for the benchmark
```

This file is useful because it shows that the benchmark can be reproduced outside Jupyter.

### `fixed_policy.ipynb`

This notebook tests simple fixed ramp-metering policies. Instead of solving an optimization problem, it scales
the observed ramp-release command by a fixed multiplier:

```text
u_fixed = s × observed_release
```

where `s` is the fixed release scale. The notebook tests several release scales and evaluates each policy
through the same exact CTM simulator used by the benchmark. This makes it a fair simple-policy baseline.

```text
fixed_policy.ipynb = simple fixed-release comparison
```

The purpose of this notebook is to answer: *does the optimized controller actually do something smarter than
simply releasing more or fewer ramp vehicles with a fixed multiplier?* The fixed-policy notebook is an important
ablation because it prevents overclaiming. If a simple fixed release scale already performs well, then the
optimized controller must beat that baseline to be meaningful.

### `Benchmark_convex_QP.ipynb`

This notebook defines the centralized convex QP surrogate of the ramp-metering control problem. The exact CTM
benchmark contains nonconvex and nonsmooth components, including:

- minimum sending/receiving flow rules,
- merge-priority switching,
- receiving-aware ramp acceptance,
- physical queue and spillback splitting,
- clipped delay and capacity-violation terms.

Because of these exact min/max and switching relationships, the exact CTM-based control problem is difficult to
optimize globally. To obtain a tractable optimization reference, this notebook builds a convex surrogate. It
replaces exact switching rules with convex capacity constraints and uses epigraph/slack variables for delay and
penalty terms. The result is a centralized convex quadratic program that can be solved to a global optimum for
the surrogate model.

```text
Benchmark_convex_QP.ipynb = centralized convex QP reference model
```

**Important distinction.** The convex QP is not the exact historical benchmark replay. It is a convex
surrogate/reference model derived from the benchmark CTM. In the uploaded setup, it uses `AW = 1` and solves the
centralized convex surrogate to an internal QP objective of approximately 52,637. This value is the optimum of
the surrogate model, not the realized exact-CTM objective. When the QP commands are replayed through the exact
CTM, the realized raw objective is much higher, approximately 170,560, because the convex relaxation is looser
than the exact merge and min/max CTM dynamics. Therefore, the QP is a centralized optimization reference, not a
realized controller result.

### `ADMM_MPC.ipynb`

This is the main optimization/controller notebook. It uses the same CTM setup and benchmark inputs, but instead
of applying a fixed rule, it repeatedly solves a short-horizon convex traffic-control problem. At each 15-second
time step, it:

1. observes the current exact CTM state,
2. solves a short-horizon convex QP surrogate over the next `K` steps,
3. applies only the first optimized ramp-metering command,
4. advances the exact CTM by one step,
5. repeats the process.

This is a receding-horizon MPC structure:

```text
plan → apply first command → update exact CTM state → replan
```

```text
ADMM_MPC.ipynb = lookahead MPC controller using the convex QP surrogate
```

The notebook also includes representative two-block ADMM checks. These checks verify that, on tested
representative MPC windows, the centralized QP solution and the two-block ADMM solution produce nearly identical
first commands. This supports the interpretation that, for the tested MPC windows, the centralized QP solution
and the converged two-block ADMM solution are numerically equivalent in the first command applied to the exact
CTM.

**Important distinction.** ADMM convergence is a statement about the convex surrogate subproblem, not about the
original nonlinear CTM. The final controller performance is still evaluated by replaying the applied commands
through the exact CTM, not by trusting only the convex surrogate.

### `shared_benchmark_inputs.pkl`

This is the single shared input file exported by `Benchmark_calculation.ipynb` and loaded by the other
notebooks.

```text
shared_benchmark_inputs.pkl = shared data and parameters for every model
```

It exists to ensure consistency. All models use the same initial states, arrivals, capacities, ramp storage
limits, free-flow travel times, objective weights, and benchmark denominators.

---

## 3. Shared Input Design

The project uses one shared input file:

```text
shared_benchmark_inputs.pkl
```

The purpose is consistency. It prevents the benchmark, fixed-policy baseline, convex QP, and ADMM-MPC controller
from silently using different assumptions. The shared file includes:

- mainline initial state,
- ramp initial queues,
- ramp arrival series,
- observed release series,
- uncontrolled external inflow series,
- fixed local outflow series,
- upstream boundary demand,
- inflow capacities,
- safe-threshold capacities,
- physical storage capacities,
- ramp storage limits,
- free-flow travel times,
- objective weights,
- official benchmark totals,
- normalization denominators.

The project treats ramp arrivals as fixed external demand. Ramp arrivals are not recomputed from the optimizer's
release decisions. This is important because the controller should not be allowed to "reduce demand" simply by
holding vehicles back.

---

## 4. Corridor Setup

The corridor is modeled as:

- 9 freeway mainline CTM cells,
- 4 controlled on-ramps,
- 15-second time step,
- 480 simulation steps,
- 2-hour simulation window.

The time step is:

```text
Δt = 15 seconds = 0.25 minutes
```

The controlled ramps are:

```text
4th
Price
Mattie
Avila
```

The ramp-to-cell mapping is:

```text
4th    → Cell 2
Price  → Cell 2
Mattie → Cell 6
Avila  → Cell 9
```

Avila is special because it merges into the final cell, Cell 9. It uses a priority merge rule with priority:

```text
π = 0.3
```

This gives Avila a priority share of Cell 9 receiving capacity when Avila and the Cell 8 mainline flow compete
for the same downstream space.

---

## 5. CTM Modeling Setup

The freeway is simulated using a Cell Transmission Model. Each mainline cell has:

- vehicle count / occupancy,
- sending capacity,
- receiving capacity,
- inflow capacity,
- safe occupancy threshold,
- physical storage capacity,
- fixed local outflow,
- mainline inflow,
- mainline outflow.

At every 15-second step, vehicles move from one cell to the next subject to sending and receiving limits. The
exact benchmark CTM uses receiving-aware flow logic:

```text
actual flow cannot exceed upstream sending capacity
actual flow cannot exceed downstream receiving capacity
```

Uncontrolled external inflow consumes receiving capacity first. Controlled ramp releases are then accepted only
if the receiving cell has space. The final cell, Cell 9, discharges traffic out of the modeled corridor.

---

## 6. Ramp Queue Setup

Each ramp has two queue quantities:

- `R` — physical ramp queue,
- `B` — spillback beyond ramp storage.

At every time step, ramp-side demand is updated by:

```text
new waiting demand = old physical queue + old spillback + new ramp arrivals − accepted ramp release
```

If the waiting demand fits inside ramp storage, it becomes physical queue `R`. If it exceeds ramp storage, the
physical queue is capped and the excess becomes spillback `B`. So:

```text
R = queue stored physically on the ramp
B = overflow beyond ramp storage
```

Spillback represents demand that cannot fit on the ramp and affects the local road network.

---

## 7. Main Assumptions

### 1. Ramp arrivals are estimated

PeMS ramp detectors measure released/discharged vehicles, not the true number of vehicles that wanted to enter
the ramp. Therefore, ramp arrivals are estimated as:

```text
ramp_arrival = arrival_multiplier × observed_release
```

The final official setup uses:

```text
arrival_multiplier = 1.2
```

This is an assumption and should be interpreted as a stress-demand scenario.

### 2. Ramp arrivals are external demand

Ramp arrivals are treated as fixed exogenous demand. They are not recomputed based on the optimized release.
This prevents the controller from artificially improving results by lowering demand.

### 3. Negative delay is clamped to zero

The state-based delay formula can become slightly negative in some cells because of the relationship between the
time step and free-flow travel time. Since physical delay cannot be negative, per-cell delay is clamped at zero.
This convention is applied consistently across the benchmark, fixed-policy, convex QP, and ADMM-MPC evaluations.

### 4. Safe capacity and physical capacity are different

The safe threshold is an operational congestion threshold. The physical capacity is the hard storage limit. A
cell can exceed the safe threshold without exceeding physical capacity. These violations are penalized
separately.

### 5. Spillback is penalized separately and linearly

Ramp demand beyond physical ramp storage is counted as spillback. The final objective penalizes spillback
linearly:

```text
spillback penalty = λ₄ · B
```

The project previously tested a quadratic spillback penalty, but the final setup uses the linear version to
avoid making spillback overwhelmingly dominate the total objective.

### 6. All models use the same shared inputs

Benchmark, fixed policy, convex QP, and ADMM-MPC all load the same shared input file. This keeps capacities,
arrivals, initial states, and objective weights consistent across comparisons.

---

## 8. Objective Function Setup

The objective combines several terms:

```text
raw objective =
    mainline delay
  + ramp delay
  + fairness penalty
  + doorway penalty
  + safe-threshold penalty
  + physical-capacity penalty
  + spillback penalty
```

**Mainline delay** measures freeway congestion inside the CTM cells and the upstream boundary queue. It uses
vehicle-minutes in each cell minus the free-flow travel-time contribution of vehicles leaving the cell. Negative
per-cell delay is clamped to zero.

**Ramp delay** measures waiting time on ramps and in spillback queues. It uses the average ramp-side queue over
each time step:

```text
physical ramp queue + spillback queue
```

**Fairness penalty** measures imbalance in physical ramp queue stress across ramps. Physical ramp stress is:

```text
φ_r = clip(R_r / R_r^max, 0, 1)
```

The fairness penalty sums squared differences between pairs of ramp stresses. **Important:** fairness uses
physical queue `R`, not spillback `B`. Spillback is penalized separately.

**Doorway penalty** punishes excess pressure into a cell beyond the cell's inflow capacity. It is a squared
positive-part penalty.

**Safe-threshold penalty** punishes mainline occupancy above the safe occupancy threshold. It is a squared
positive-part penalty.

**Physical-capacity penalty** punishes mainline occupancy above hard physical storage capacity. It is also a
squared positive-part penalty.

**Spillback penalty** punishes ramp overflow beyond ramp storage. The final model uses `λ₄ · B`, so the
spillback penalty is linear.

---

## 9. Normalization Setup

Some controller objectives use benchmark denominators to normalize terms with very different magnitudes. For
example, mainline delay, ramp delay, safe penalty, and spillback penalty can have different numerical scales.
Normalization prevents one term from dominating only because of its units.

The benchmark notebook computes normalization denominators from the official benchmark history and exports them
through `shared_benchmark_inputs.pkl`. These denominators are used where needed by the controller tuning and
comparison logic.

---

## 10. Controller and Optimization Setup

### Benchmark

The benchmark replays the historical observed ramp-release commands. It does not optimize. It answers: *what
happens under the observed historical ramp-release behavior?* This is the baseline.

### Fixed Policy

The fixed-policy baseline scales the historical observed ramp release by a constant multiplier. It answers:
*can a simple fixed release rule beat the historical benchmark?* This is the main non-optimization baseline. The
best fixed policy in the final setup is:

```text
release scale = 1.10
```

This improves the raw objective compared with the benchmark, but it is not adaptive.

### Centralized Convex QP

The convex QP solves the entire horizon at once under a convex surrogate of the CTM dynamics. It answers: *what
is the centralized optimum of the convex surrogate model?* It is not the exact benchmark replay, and it is not
the final realized controller evaluation. It is a mathematical reference model. In the uploaded setup, it runs
at mainline weight:

```text
AW = 1
```

Its internal convex-surrogate optimum is approximately `52,637`. However, when those QP commands are replayed
through the exact CTM, the realized raw objective is approximately `170,560`. This gap exists because the convex
surrogate is looser than the exact CTM merge and min/max dynamics. Therefore, the centralized convex QP is used
only as an optimization reference, not as a realized controller result.

### ADMM-MPC

ADMM-MPC is the final controller. It repeatedly solves a short-horizon convex traffic-control problem, applies
the first optimized ramp command, updates the exact CTM state, and replans. It answers: *can a lookahead
adaptive controller outperform the benchmark, fixed policy, and open-loop plan when evaluated through the exact
CTM?* The final system-objective setting is:

```text
K     = 10
AW    = 2.4
METER = arrival_multiplier = 1.2
```

The controller is evaluated using exact CTM replay, not only the convex surrogate.

---

## 11. How the Files Work Together

```text
0. Raw PeMS data
   d05_text_meta_2026_04_28.txt
   d05_text_station_5min_2026_05_27.txt

1. Benchmark_calculation.ipynb
   → reads raw PeMS files
   → builds the 9-cell CTM
   → computes the historical observed-command benchmark
   → validates the benchmark replay
   → exports shared_benchmark_inputs.pkl

2. Benchmark_calculation.py
   → loads shared_benchmark_inputs.pkl
   → reruns the benchmark
   → verifies exact reproduction outside Jupyter

3. fixed_policy.ipynb
   → loads the same benchmark setup
   → tests simple fixed release scales
   → identifies the best fixed-policy baseline

4. Benchmark_convex_QP.ipynb
   → loads shared_benchmark_inputs.pkl
   → builds the centralized convex QP surrogate
   → solves the convex reference problem

5. ADMM_MPC.ipynb
   → loads shared_benchmark_inputs.pkl
   → runs receding-horizon optimization
   → checks representative ADMM/QP agreement
   → evaluates applied commands through the exact CTM
   → compares against benchmark, fixed policy, and open-loop control
```

---

## 12. Final Result Summary

The final comparison uses exact CTM replay for realized controller performance. Approximate final raw objectives
are:

```text
Historical benchmark:        130,423
Best fixed policy:            83,436
Open-loop full-horizon plan:  73,415
ADMM-MPC:                     61,218
```

The final ADMM-MPC setting is `K = 10`, `AW = 2.4`. This gives the lowest total raw objective among the tested
benchmark, fixed-policy, open-loop, and MPC policies. It improves the raw objective by approximately:

```text
53.1% compared with the historical benchmark
26.6% compared with the best fixed policy
16.6% compared with the open-loop controller
```

> **Note on the open-loop number.** The open-loop full-horizon plan, approximately 73,415, is produced by
> solving the same convex QP family at the open-loop-tuned mainline weight (`AW ≈ 3.2`) under the metering cap,
> then replaying the resulting commands through the exact CTM. It is the same QP family as
> `Benchmark_convex_QP.ipynb`, but at a different weight. The `AW = 1` reference QP would instead replay to
> approximately 170,560 on the exact CTM. All four numbers above are exact-CTM realized values.

---

## 13. Important Reporting Note

The results should not be described as: *"ADMM-MPC is universally better in every possible metric."* The correct
framing is: *"ADMM-MPC improves the total system objective by managing the freeway-ramp trade-off."*

The controller trades off mainline delay, ramp delay, spillback, fairness, and capacity penalties. A higher
mainline weight can reduce mainline delay more aggressively, but it may increase ramp delay and spillback.
Therefore, the defensible claim is: *ADMM-MPC achieves the best total raw objective among the tested policies
under the final system-objective setting.*

A separate mainline-priority sensitivity can also be reported, but it should be clearly labeled as a sensitivity
case rather than the main system-objective optimum.

---

## 14. Convex QP and ADMM Interpretation

The convex QP and ADMM-MPC should be interpreted carefully. The exact benchmark CTM is the source-of-truth
evaluator. The convex QP is a surrogate optimization model. ADMM convergence applies to the convex surrogate
subproblem, not to the original nonlinear CTM. The realized controller performance is therefore always reported
using exact CTM replay.

This separation is important:

```text
Convex QP = optimization reference
ADMM-MPC  = adaptive controller
Exact CTM = final evaluator
```

This makes the project defensible because it avoids claiming that the convex surrogate is identical to the exact
CTM, while still using the surrogate to build a tractable and effective controller.
