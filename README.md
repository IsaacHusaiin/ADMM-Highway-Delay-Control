# Highway Corridor Delay Optimization with CTM, Greedy ADMM, and ADMM-MPC

This project models and optimizes traffic delay on **I-405 southbound** using **Caltrans PeMS** data, an **8-cell Cell Transmission Model (CTM)**, a **Greedy ADMM ramp-metering controller**, and a **rolling-horizon ADMM-MPC controller**.

The main goal is to reduce freeway corridor congestion while accounting for:

- mainline delay
- local ramp delay
- fairness across ramps
- doorway-capacity protection
- safe-threshold occupancy protection
- physical-capacity protection
- ramp spillback

The final project compares three main cases:


1. Benchmark:
   Observed-release baseline using PeMS-derived ramp releases.

2. Greedy ADMM:
   One-step ADMM controller.
   Optimizes only the current 30-second timestep.

3. ADMM-MPC:
   Rolling-horizon ADMM-MPC controller.
   Optimizes over a future prediction horizon.
Main result

The final benchmark-vs-ADMM-MPC comparison shows that ADMM-MPC substantially improves the corridor objective and total system delay.

Metric	Benchmark	ADMM-MPC	Change
Normalized weighted objective	34.000	20.950	-38.383%
Total system delay	88,074.345 veh-min	60,445.876 veh-min	-31.37%
Mainline delay	72,848.691 veh-min	44,529.476 veh-min	-38.874%
Local ramp delay	15,225.654 veh-min	15,916.400 veh-min	+4.537%
Fairness penalty	25.453	3.307	-87.008%
Doorway penalty	5,712.108	1,088.340	-80.947%
Safe-threshold penalty	1,410,495.372	522,358.525	-62.966%
Physical-capacity penalty	0.000	0.000	0.000%
Spillback penalty	3,454.202	7,330.142	+112.209%
Capacity penalty	1,419,661.681	530,777.007	-62.612%
Raw objective	1,507,761.479	591,226.190	-60.788%

The ADMM-MPC controller greatly reduces mainline delay and safe-threshold violations, while allowing a modest increase in local ramp delay and a larger increase in spillback penalty. This tradeoff is expected because ramp metering holds more vehicles at ramps to protect freeway mainline conditions.

Greedy ADMM result

The project also includes a repaired and updated Greedy ADMM notebook.

Greedy ADMM is a simpler one-step ADMM controller. It solves one 30-second control problem at a time and does not use a future prediction horizon.

Best tested Greedy ADMM setting:

meter_multiplier = 1.0
min_admm_iters = 150
max_admm_iters = 150
Metric	Benchmark	Greedy ADMM	Change
Normalized weighted objective	34.000	32.206	-5.277%
Total system delay	88,074.345 veh-min	85,688.209 veh-min	-2.709%

This shows that one-step ADMM improves over the observed-release benchmark, but the improvement is much smaller than ADMM-MPC.

The main interpretation is:

Greedy ADMM proves that one-step ADMM can improve the benchmark modestly.
ADMM-MPC proves that rolling-horizon lookahead is much more powerful.
Corridor and dataset

Source: Caltrans PeMS
Facility: I-405 Southbound
Postmile range: 8.17 to 13.07
Corridor length: 4.90 miles
Observed study period: 2026-01-08, 08:00–09:00
Original PeMS data interval: 5 minutes
Simulation timestep: 30 seconds
Simulation horizon: 120 steps = 60 minutes

Selected mainline stations
Variable	Station ID	Location	Abs PM
Boundary inflow	1201419	RED HILL	8.17
Mainline 1	1201469	BRISTOL 1	9.31
Mainline 2	1201497	FAIRVIEW	10.05
Mainline 3	1201525	HARBOR 1	10.97
Mainline 4	1201558	HARBOR 2	11.27
Mainline 5	1201589	EUCLID	12.27
Downstream station	1201620	TALBERT	13.07
Selected on-ramps
Variable	Station ID	Location	Abs PM
u1	1201460	BRISTOL 1	9.31
u2	1201490	FAIRVIEW	10.07
u3	1201517	HARBOR 1	10.97
u4	1201548	HARBOR 2	11.27
u5	1201580	EUCLID	12.27
Selected off-ramps
Variable	Station ID	Location	Abs PM
f1	1201465	BRISTOL 1	9.31
f2	1201554	HARBOR 2	11.27
f3	1201585	EUCLID	12.27
Ramp-location figures

The ramp_figure/ folder contains Google Earth screenshots used as supporting visual references for selected ramp locations.

Ramp lengths were also measured using Google Earth and used as supporting geometric reference values for ramp storage assumptions.

CTM redesign

The original prototype used a coarser 6-cell, 5-minute CTM. The final model uses a finer and more physically valid discretization:

8 CTM cells
30-second timestep

The CFL condition is:

Δx
v
ff
	​

ΔT
	​

≤1

Using the corridor median overnight free-flow speed:

v
ff
	​

=68.1 mph

and:

Δx=
8
4.90
	​

=0.6125 miles
ΔT=30 sec=
120
1
	​

 hr

gives:

0.6125
68.1×(1/120)
	​

=0.927≤1

Therefore, the 8-cell, 30-second CTM satisfies the CFL condition.

8-cell CTM network
Cell	Abs PM Range	On-ramp(s)	Off-ramp(s)
Cell 1	8.1700 – 8.7825	none	none
Cell 2	8.7825 – 9.3950	u1 BRISTOL 1	f1 BRISTOL 1
Cell 3	9.3950 – 10.0075	none	none
Cell 4	10.0075 – 10.6200	u2 FAIRVIEW	none
Cell 5	10.6200 – 11.2325	u3 HARBOR 1	none
Cell 6	11.2325 – 11.8450	u4 HARBOR 2	f2 HARBOR 2
Cell 7	11.8450 – 12.4575	u5 EUCLID	f3 EUCLID
Cell 8	12.4575 – 13.0700	none	none
Lane-count assumption

The final corrected lane-count setup is:

Cell 5 = 6 lanes
Cell 7 = 6 lanes
All other cells = 5 lanes

This corrected lane count is used consistently in the benchmark, Greedy ADMM, and ADMM-MPC notebooks.

CTM capacity structure

The CTM uses three capacity-related concepts:

Doorway capacity:
Maximum flow that can enter a cell during one timestep.

Safe-threshold capacity:
A soft occupancy threshold. Exceeding this creates a safe-threshold penalty.

Physical capacity:
A hard storage-capacity reference based on jam density.

Capacity protection terms include:

doorway overflow penalty
safe-threshold occupancy penalty
physical-capacity penalty
ramp spillback penalty

In the final simulations, physical-capacity penalty remains inactive, meaning no cell exceeds hard physical storage. The main capacity issue is safe-threshold violation, especially in congested mainline cells.

Delay model
Mainline delay

The project uses a state-based mainline delay calculation based on cell occupancy, next-state occupancy, discharged flow, off-ramp flow, and free-flow travel time.

This is more suitable for dynamic control than a purely flow-based delay metric because it accounts for stored vehicles and CTM state evolution.

Local ramp delay

Ramp delay is computed from queue evolution:

R
i,t+1
	​

=R
i,t
	​

+a
i,t
	​

−u
i,t
	​


where:

R_i,t = ramp queue
a_i,t = ramp arrival
u_i,t = controlled ramp release

Local delay is computed from average queue length over the timestep.

Fairness penalty

Ramp stress is normalized by ramp storage capacity:

ϕ
i,t
cap
	​

=min(
R
max,i
	​

R
i,t
	​

	​

,1)

Fairness penalizes imbalance across ramp queue stress levels.

Spillback penalty

If the raw ramp queue exceeds the maximum ramp storage, the excess is treated as spillback:

spillback
i,t
	​

=max(0,R
i,t
raw
	​

−R
max,i
	​

)

Spillback is penalized quadratically.

Objective function

The raw objective is:

L(t)=L
mainline
	​

(t)+L
local
	​

(t)+L
fair
	​

(t)+L
cap
	​

(t)

where:

L_mainline = mainline delay
L_local = local ramp delay
L_fair = fairness penalty
L_cap = capacity-related penalty

The capacity penalty is:

L
cap
	​

=P
door
	​

+P
safe
	​

+P
phys
	​

+P
spill
	​


where:

P_door = doorway overflow penalty
P_safe = safe-threshold occupancy penalty
P_phys = physical-capacity penalty
P_spill = ramp spillback penalty
Objective normalization

The raw terms have very different numerical scales. For example, safe-threshold penalties can be much larger than delay or fairness terms.

Therefore, the project uses benchmark-normalized terms:

D
~
main
	​

=
D
main
benchmark
	​

D
main
	​

	​

D
~
local
	​

=
D
local
benchmark
	​

D
local
	​

	​


and similarly for fairness, doorway, safe-threshold, physical-capacity, and spillback penalties.

The normalized weighted objective is:

J=α
main
	​

D
~
main
	​

+β
local
	​

D
~
local
	​

+
P
~
fair
	​

+
P
~
door
	​

+
P
~
safe
	​

+
P
~
phys
	​

+
P
~
spill
	​


The final controller tradeoff weights are:

alpha_main = 30.0
beta_local = 1.0

The official benchmark normalized objective is:

34.000
Benchmark simulation

The benchmark simulation uses observed ramp releases and the official PeMS-derived input series.

The benchmark totals are:

Metric	Benchmark
Mainline delay	72,848.691
Local delay	15,225.654
Fairness penalty	25.453
Doorway penalty	5,712.108
Safe-threshold penalty	1,410,495.372
Physical-capacity penalty	0.000
Spillback penalty	3,454.202
Capacity penalty	1,419,661.681
Raw objective	1,507,761.479
Normalized weighted objective	34.000
Total system delay	88,074.345
Greedy ADMM framework

Greedy ADMM solves one ramp-metering problem at each 30-second timestep.

It splits the optimization into two ADMM blocks.

Ramp-side block

The ramp-side block optimizes:

local ramp delay
fairness penalty
spillback penalty
Freeway-side block

The freeway-side block optimizes:

mainline delay
doorway penalty
safe-threshold penalty
physical-capacity penalty

ADMM coordinates the two variable copies:

u = ramp-side release decision
z = freeway-side release decision

The ADMM loop is:

1. Update u using the ramp-side problem.
2. Update z using the freeway-side problem.
3. Update the dual variable.
4. Check primal and dual residuals.

Greedy ADMM has no future lookahead.

Greedy ADMM sensitivity result

The Greedy ADMM notebook tests multiple meter-capacity multipliers and ADMM iteration settings.

The meter-capacity rule is:

meter_capacity = meter_multiplier × observed_release

The sensitivity experiment shows that increasing the ADMM minimum iteration count improves the one-step ADMM solution when the meter multiplier is 1.0.

Meter multiplier	Min ADMM iters	Max ADMM iters	Normalized objective	Objective change	Delay change
1.0	20	150	33.586	-1.218%	-0.566%
1.0	50	150	33.129	-2.562%	-1.219%
1.0	100	150	32.578	-4.182%	-2.088%
1.0	150	150	32.206	-5.277%	-2.709%

However, increasing the meter-capacity multiplier above 1.0 worsens the result because it releases more vehicles into an already congested freeway.

Meter multiplier	Best normalized objective	Best objective change
1.0	32.206	-5.277%
1.1	36.452	+7.212%
1.2	40.697	+19.696%
1.5	54.121	+59.181%
2.0	54.121	+59.181%

This indicates that the main bottleneck is the freeway mainline, not insufficient ramp discharge capacity.

ADMM-MPC framework

ADMM-MPC extends the one-step ADMM idea into a rolling-horizon controller.

Instead of optimizing only the current 30-second timestep, ADMM-MPC optimizes over a future prediction horizon, applies the first ramp-release decision, then rolls the horizon forward.

This allows ADMM-MPC to account for:

future mainline congestion
future ramp arrivals
future spillback pressure
future capacity violations
future queue imbalance

This is why ADMM-MPC performs much better than Greedy ADMM.

ADMM-MPC final result

The official ADMM-MPC totals are:

Metric	ADMM-MPC
Mainline delay	44,529.476
Local delay	15,916.400
Fairness penalty	3.307
Doorway penalty	1,088.340
Safe-threshold penalty	522,358.525
Physical-capacity penalty	0.000
Spillback penalty	7,330.142
Capacity penalty	530,777.007
Raw objective	591,226.190
Normalized weighted objective	20.950
Total system delay	60,445.876

Compared with the benchmark, ADMM-MPC achieves:

Normalized objective reduction = 38.383%
Total system delay reduction = 31.37%
Mainline delay reduction = 38.874%
Safe-threshold penalty reduction = 62.966%
Fixed-policy ablation

The project also includes a fixed-policy ablation that tests simple constant ramp-release scaling policies.

At arrival multiplier 1.5:

Policy	Total system delay	Normalized objective	Spillback penalty
Baseline fixed 1.0x	88,074.3	34.000	3,454.202
Fixed 0.9x	75,955.4	28.617	5,088.150
Fixed 0.8x	63,869.5	23.418	7,039.258
Fixed 0.7x	51,657.1	18.277	9,300.842
ADMM-MPC	60,445.9	20.950	7,330.142

The fixed 0.7x policy has the lowest objective in this ablation, but it rejects the most ramp demand and produces the highest spillback. It is therefore not directly equivalent to an adaptive controller.

The interpretation is:

ADMM-MPC improves substantially over the observed-release benchmark and moderate fixed policies.
Very restrictive fixed policies can reduce freeway delay further, but mainly by holding or spilling more ramp demand.
Demand accounting

Demand accounting is included to check whether a policy improves the objective by serving vehicles efficiently or simply by rejecting ramp demand.

For arrival multiplier 1.5:

Policy	Released	Queued	Spilled	Served rate	Spill rate
Baseline	4,200.0	278.5	1,821.5	66.7%	28.9%
Fixed 0.9x	3,780.0	278.5	2,241.5	60.0%	35.6%
Fixed 0.8x	3,360.0	278.5	2,661.5	53.3%	42.2%
Fixed 0.7x	2,940.0	278.5	3,081.5	46.7%	48.9%
ADMM-MPC	3,290.6	278.5	2,730.9	52.2%	43.3%

This confirms that aggressive ramp restriction can improve freeway metrics while shifting more delay or rejection to ramps.

Repository structure

The repository includes notebooks and scripts for:

Benchmark calculation
8-cell CTM simulation
Greedy ADMM controller
ADMM-MPC controller
Fixed-policy ablation
Sensitivity experiments
Ramp-location figures

The benchmark notebook exports shared source-of-truth variables used by Greedy ADMM and ADMM-MPC.

Current project status

Completed:

- corridor and station selection
- PeMS data processing
- 8-cell CTM redesign
- CFL validation
- initial mainline state reconstruction
- ramp arrival and queue setup
- off-ramp flow integration
- state-based mainline delay model
- local ramp delay model
- fairness penalty model
- doorway-capacity penalty
- safe-threshold penalty
- physical-capacity penalty
- spillback penalty
- benchmark CTM simulation
- objective normalization
- Greedy ADMM one-step controller
- Greedy ADMM 120-step simulation
- Greedy ADMM sensitivity experiment
- ADMM-MPC rolling-horizon controller
- ADMM-MPC convergence diagnostics
- fixed-policy ablation
- demand accounting comparison

Future extensions:

- test additional days and time windows
- calibrate against more PeMS observations
- evaluate multiple congestion scenarios
- test alternative fairness definitions
- test alternative ramp-metering constraints
- add stronger demand-service constraints
- compare against classical ramp-metering methods
- improve visualization and dashboard reporting
Main conclusion

This project shows that dynamic ramp metering can substantially reduce freeway corridor congestion when modeled with a physically consistent CTM and optimized with ADMM-MPC.

The final interpretation is:

Benchmark:
Observed-release baseline with high mainline delay and safe-threshold violations.

Greedy ADMM:
One-step optimization.
Improves over benchmark modestly.

ADMM-MPC:
Rolling-horizon optimization.
Improves over benchmark substantially.

Fixed restrictive policies:
Can reduce freeway delay, but often by rejecting or spilling more ramp demand.

The strongest modeling conclusion is that lookahead matters.

Greedy ADMM shows that ADMM decomposition alone gives modest improvement. ADMM-MPC shows that adding a rolling prediction horizon produces much stronger improvements in mainline delay, safe-threshold protection, and total normalized objective.
