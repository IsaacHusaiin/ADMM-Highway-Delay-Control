"""
Official 9-cell / 15-second CTM benchmark reproduction script.

"""
from pathlib import Path
import pickle
from typing import Any

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_INPUTS_PATH = SCRIPT_DIR / "shared_benchmark_inputs.pkl"
if not SHARED_INPUTS_PATH.exists():
    raise FileNotFoundError(
        "shared_benchmark_inputs.pkl was not found next to this script. "
        "Run the export cell in Benchmark_calculation.ipynb first."
    )
with open(SHARED_INPUTS_PATH, "rb") as _f:
    shared: dict[str, Any] = pickle.load(_f)


def get_input(name: str) -> Any:
    if name not in shared:
        raise KeyError(f"{name} was not found in shared_benchmark_inputs.pkl")
    return shared[name]


def get_optional_input(name: str, default_value: Any) -> Any:
    return shared[name] if name in shared else default_value


# --- Geometry / ids / mapping (globals referenced by the engine functions) ---
cell_ids = [f"Cell {i}" for i in range(1, 10)]
ramp_ids = list(get_input("ramp_ids"))
ramp_cell_map = get_input("ramp_cell_map")
generic_ramp_cell_map = get_input("generic_ramp_cell_map")
merge_ramp_id = get_input("merge_ramp_id")
merge_ramp_cell = get_input("merge_ramp_cell")
MERGE_PRIORITY = float(get_input("MERGE_PRIORITY"))
delta_t = float(get_input("delta_t"))
num_steps = int(get_input("num_steps"))
use_clipped_mainline_delay = bool(get_optional_input("use_clipped_mainline_delay", True))
arrival_multiplier = float(get_optional_input("arrival_multiplier", 1.2))

official_totals = get_input("official_totals")
official_service_metrics = get_optional_input("official_service_metrics", {})

# Guard: make sure this is the FINAL linear-spillback benchmark, not an old quadratic one.
if float(official_totals["raw_objective"]) > 1_000_000:
    raise RuntimeError(
        "The loaded pickle looks like the OLD quadratic-spillback benchmark. "
        "Re-run the final linear-spillback Benchmark_calculation.ipynb to refresh it."
    )

# Setup sanity checks.
assert num_steps == 480, num_steps
assert abs(delta_t - 0.25) < 1e-12, delta_t
assert cell_ids == [f"Cell {i}" for i in range(1, 10)]
assert len(ramp_ids) == 4, ramp_ids
assert merge_ramp_id == "u_avila", merge_ramp_id
assert merge_ramp_cell == "Cell 9", merge_ramp_cell
assert merge_ramp_id not in generic_ramp_cell_map


# ENGINE BELOW IS COPIED VERBATIM FROM Benchmark_calculation.ipynb (do not edit by hand;
# regenerate from the notebook if the benchmark changes).

# 6. Penalties, ramp queue, receiving-aware CTM step, delay, full simulation
# FAIRNESS PENALTY SETUP
gamma = 1.0

def fairness_penalty_one_step(
    R_next,
    ramp_name_map,
    ramp_max_queue_named,
    gamma
):
    stress_dict = {}

    for u_name, R_t in R_next.items():
        if u_name not in ramp_name_map:
            raise KeyError(f"{u_name} missing from ramp_name_map")

        ramp_name = ramp_name_map[u_name]

        if ramp_name not in ramp_max_queue_named:
            raise KeyError(f"{ramp_name} missing from ramp_max_queue_named")

        R_max_i = float(ramp_max_queue_named[ramp_name])

        if R_max_i <= 0:
            raise ValueError(f"Invalid R_max for {ramp_name}: {R_max_i}")

        raw_stress = float(R_t) / R_max_i
        capped_stress = min(max(raw_stress, 0.0), 1.0)

        stress_dict[ramp_name] = capped_stress

    ramps = list(stress_dict.keys())
    fairness_sum = 0.0

    for i in range(len(ramps)):
        for j in range(i + 1, len(ramps)):
            phi_i = stress_dict[ramps[i]]
            phi_j = stress_dict[ramps[j]]

            fairness_sum += (phi_i - phi_j) ** 2

    L_fair = gamma * fairness_sum

    return stress_dict, fairness_sum, L_fair


# RAMP REQUESTS BEFORE MAINLINE MERGE ACCEPTANCE
def ramp_requested_release_one_step(
    R_current,
    B_current,
    ramp_arrival_step,
    commanded_release_step
):
    available_demand_step = {}
    requested_release_step = {}

    for ramp in ramp_ids:
        if ramp not in R_current:
            raise KeyError(f"{ramp} missing from R_current")

        if ramp not in B_current:
            raise KeyError(f"{ramp} missing from B_current")

        if ramp not in ramp_arrival_step:
            raise KeyError(f"{ramp} missing from ramp_arrival_step")

        if ramp not in commanded_release_step:
            raise KeyError(f"{ramp} missing from commanded_release_step")

        available = (
            max(0.0, float(R_current[ramp]))
            + max(0.0, float(B_current[ramp]))
            + max(0.0, float(ramp_arrival_step[ramp]))
        )

        request = min(
            max(0.0, float(commanded_release_step[ramp])),
            available
        )

        available_demand_step[ramp] = available
        requested_release_step[ramp] = request

    return available_demand_step, requested_release_step


# RAMP QUEUE UPDATE AFTER RECEIVING-AWARE ACTUAL RELEASES
def ramp_next_queue_after_actual_release(
    available_demand_step,
    actual_release_step,
    ramp_max_queue_by_u
):
    R_next = {}
    B_next = {}
    spillback_by_ramp = {}

    for ramp in ramp_ids:
        if ramp not in available_demand_step:
            raise KeyError(f"{ramp} missing from available_demand_step")

        if ramp not in actual_release_step:
            raise KeyError(f"{ramp} missing from actual_release_step")

        if ramp not in ramp_max_queue_by_u:
            raise KeyError(f"{ramp} missing from ramp_max_queue_by_u")

        available = max(0.0, float(available_demand_step[ramp]))
        actual_release = max(0.0, float(actual_release_step[ramp]))
        R_max = float(ramp_max_queue_by_u[ramp])

        if R_max <= 0:
            raise ValueError(f"Invalid R_max for {ramp}: {R_max}")

        if actual_release - available > 1e-9:
            raise ValueError(
                f"Actual release exceeds available demand for {ramp}: "
                f"actual={actual_release}, available={available}"
            )

        waiting_after_release = max(
            0.0,
            available - actual_release
        )

        R_next[ramp] = min(
            waiting_after_release,
            R_max
        )

        B_next[ramp] = max(
            0.0,
            waiting_after_release - R_max
        )

        spillback_by_ramp[ramp] = B_next[ramp]

    return R_next, B_next, spillback_by_ramp


# CAPACITY PENALTY FUNCTION FOR 9-CELL / 15-SEC CTM
lambda_1 = 1.0   # doorway demand pressure penalty weight
lambda_2 = 0.5   # safe threshold penalty weight
lambda_3 = 1.0   # physical capacity penalty weight
lambda_4 = 0.5   # spillback penalty weight

def capacity_penalty_one_step(
    q_in,
    external_inflow_step,
    controllable_onramp_in_step,
    x_next,
    inflow_capacity,
    safe_threshold_capacity,
    physical_capacity,
    spillback_by_ramp,
    lambda_1,
    lambda_2,
    lambda_3,
    lambda_4
):
    doorway_penalty_by_cell = {}
    safe_threshold_penalty_by_cell = {}
    physical_capacity_penalty_by_cell = {}
    spillback_penalty_by_ramp = {}

    total_doorway_penalty = 0.0
    total_safe_threshold_penalty = 0.0
    total_physical_capacity_penalty = 0.0
    total_spillback_penalty = 0.0

    for cell in cell_ids:
        doorway_demand_pressure = (
            float(q_in.get(cell, 0.0))
            + float(external_inflow_step.get(cell, 0.0))
            + float(controllable_onramp_in_step.get(cell, 0.0))
        )

        doorway_excess = max(
            0.0,
            doorway_demand_pressure - float(inflow_capacity[cell])
        )

        doorway_penalty = lambda_1 * doorway_excess ** 2

        doorway_penalty_by_cell[cell] = doorway_penalty
        total_doorway_penalty += doorway_penalty

        safe_excess = max(
            0.0,
            float(x_next[cell]) - float(safe_threshold_capacity[cell])
        )

        safe_penalty = lambda_2 * safe_excess ** 2

        safe_threshold_penalty_by_cell[cell] = safe_penalty
        total_safe_threshold_penalty += safe_penalty

        physical_excess = max(
            0.0,
            float(x_next[cell]) - float(physical_capacity[cell])
        )

        physical_penalty = lambda_3 * physical_excess ** 2

        physical_capacity_penalty_by_cell[cell] = physical_penalty
        total_physical_capacity_penalty += physical_penalty

    for ramp in ramp_ids:
        spillback_excess = max(
            0.0,
            float(spillback_by_ramp.get(ramp, 0.0))
        )

##changed this
        spillback_penalty = lambda_4 * spillback_excess

        spillback_penalty_by_ramp[ramp] = spillback_penalty
        total_spillback_penalty += spillback_penalty

    total_capacity_penalty = (
        total_doorway_penalty
        + total_safe_threshold_penalty
        + total_physical_capacity_penalty
        + total_spillback_penalty
    )

    return {
        "doorway_penalty_by_cell": doorway_penalty_by_cell,
        "safe_threshold_penalty_by_cell": safe_threshold_penalty_by_cell,
        "physical_capacity_penalty_by_cell": physical_capacity_penalty_by_cell,
        "spillback_penalty_by_ramp": spillback_penalty_by_ramp,
        "total_doorway_penalty": total_doorway_penalty,
        "total_safe_threshold_penalty": total_safe_threshold_penalty,
        "total_physical_capacity_penalty": total_physical_capacity_penalty,
        "total_spillback_penalty": total_spillback_penalty,
        "total_capacity_penalty": total_capacity_penalty,
    }


def allocate_ramp_requests_proportionally(
    ramps,
    requested_release_step,
    capacity_available
):
    accepted = {
        ramp: 0.0
        for ramp in ramps
    }

    capacity_available = max(
        0.0,
        float(capacity_available)
    )

    if len(ramps) == 0 or capacity_available <= 0.0:
        return accepted

    total_request = sum(
        max(0.0, float(requested_release_step[ramp]))
        for ramp in ramps
    )

    if total_request <= 0.0:
        return accepted

    if total_request <= capacity_available:
        for ramp in ramps:
            accepted[ramp] = max(
                0.0,
                float(requested_release_step[ramp])
            )

        return accepted

    for ramp in ramps:
        accepted[ramp] = (
            capacity_available
            * max(0.0, float(requested_release_step[ramp]))
            / total_request
        )

    return accepted


def build_controllable_onramp_in_from_actual_release(actual_release_step):
    controllable_onramp_in_step = {
        cell: 0.0
        for cell in cell_ids
    }

    for ramp in ramp_ids:
        if ramp not in actual_release_step:
            raise KeyError(f"{ramp} missing from actual_release_step")

        cell = ramp_cell_map[ramp]

        controllable_onramp_in_step[cell] += float(
            actual_release_step[ramp]
        )

    return controllable_onramp_in_step


# RECEIVING-AWARE 15-SECOND CTM STEP.
# Controlled ramp releases are accepted by the merge/receiving logic before entering the mainline state.
def ctm_15sec_step(
    x_current,
    q_in_boundary_step,
    external_inflow_step,
    fixed_outflow_step,
    requested_release_step,
    inflow_capacity,
    outflow_capacity,
    physical_capacity,
    movement_factor_by_cell,
    wave_speed_ratio_by_cell,
    upstream_boundary_queue=0.0,
    exit_split_by_cell=None,
    merge_priority=None
):
    cells = cell_ids

    if exit_split_by_cell is None:
        exit_split_by_cell = {
            cell: 0.0
            for cell in cells
        }

    if merge_priority is None:
        merge_priority = MERGE_PRIORITY

    assert list(exit_split_by_cell.keys()) == cells
    assert list(external_inflow_step.keys()) == cells
    assert list(fixed_outflow_step.keys()) == cells

    for ramp in ramp_ids:
        if ramp not in requested_release_step:
            raise KeyError(f"{ramp} missing from requested_release_step")

    sending_total = {}
    receiving = {}
    receiving_after_external = {}

    q_out = {
        cell: 0.0
        for cell in cells
    }

    q_in = {
        cell: 0.0
        for cell in cells
    }

    split_exit_flow = {
        cell: 0.0
        for cell in cells
    }

    actual_fixed_f_out = {}
    actual_f_out = {}
    x_next = {}

    actual_release_step = {
        ramp: 0.0
        for ramp in ramp_ids
    }

    merge_diagnostics = {
        "normal_merge_remaining_capacity": {},
        "normal_merge_ramp_requests": {},
        "normal_merge_ramp_acceptance": {},
        "avila_capacity_share": 0.0,
        "avila_request": 0.0,
        "avila_accepted": 0.0,
        "cell8_mainline_demand": 0.0,
        "cell8_mainline_accepted": 0.0,
    }

    # 1. Sending and receiving.
    for cell in cells:
        beta = float(exit_split_by_cell[cell])

        if beta < 0.0 or beta >= 1.0:
            raise ValueError(
                f"exit_split_by_cell[{cell}] must be in [0, 1). Got {beta}."
            )

        sending_total[cell] = min(
            float(movement_factor_by_cell[cell]) * float(x_current[cell]),
            float(outflow_capacity[cell])
        )

        available_storage = max(
            0.0,
            float(physical_capacity[cell]) - float(x_current[cell])
        )

        receiving[cell] = max(
            0.0,
            min(
                float(inflow_capacity[cell]),
                float(wave_speed_ratio_by_cell[cell]) * available_storage
            )
        )

        external_inflow = max(
            0.0,
            float(external_inflow_step[cell])
        )

        receiving_after_external[cell] = max(
            0.0,
            receiving[cell] - external_inflow
        )

    # 2. Boundary inflow with upstream boundary queue.
    boundary_demand = (
        float(upstream_boundary_queue)
        + float(q_in_boundary_step)
    )

    q_in["Cell 1"] = min(
        boundary_demand,
        receiving_after_external["Cell 1"]
    )

    upstream_boundary_queue_next = (
        boundary_demand
        - q_in["Cell 1"]
    )

    upstream_boundary_delay = (
        (
            float(upstream_boundary_queue)
            + float(upstream_boundary_queue_next)
        )
        / 2.0
    ) * delta_t

    # 3. Internal mainline links and ramp merge acceptance.
    normal_ramps_by_cell = {
        cell: []
        for cell in cells
    }

    for ramp, cell in ramp_cell_map.items():
        if ramp != merge_ramp_id:
            normal_ramps_by_cell[cell].append(ramp)

    for i in range(len(cells) - 1):
        cell = cells[i]
        downstream_cell = cells[i + 1]
        beta = float(exit_split_by_cell[cell])

        if 1.0 - beta <= 1e-12:
            mainline_demand = 0.0
        else:
            mainline_demand = (
                1.0
                - beta
            ) * sending_total[cell]

        downstream_capacity = receiving_after_external[downstream_cell]

        if cell == "Cell 8":
            avila_request = max(
                0.0,
                float(requested_release_step[merge_ramp_id])
            )

            avila_capacity_share = max(
                float(merge_priority) * downstream_capacity,
                downstream_capacity - mainline_demand
            )

            avila_capacity_share = max(
                0.0,
                min(
                    downstream_capacity,
                    avila_capacity_share
                )
            )

            avila_accepted = min(
                avila_request,
                avila_capacity_share
            )

            mainline_accepted = min(
                mainline_demand,
                max(
                    0.0,
                    downstream_capacity - avila_accepted
                )
            )

            actual_release_step[merge_ramp_id] = avila_accepted
            q_out[cell] = mainline_accepted

            merge_diagnostics["avila_capacity_share"] = avila_capacity_share
            merge_diagnostics["avila_request"] = avila_request
            merge_diagnostics["avila_accepted"] = avila_accepted
            merge_diagnostics["cell8_mainline_demand"] = mainline_demand
            merge_diagnostics["cell8_mainline_accepted"] = mainline_accepted

        else:
            mainline_accepted = min(
                mainline_demand,
                downstream_capacity
            )

            q_out[cell] = mainline_accepted

            remaining_capacity_for_ramps = max(
                0.0,
                downstream_capacity - mainline_accepted
            )

            ramps_feeding_downstream = normal_ramps_by_cell[downstream_cell]

            ramp_acceptance = allocate_ramp_requests_proportionally(
                ramps=ramps_feeding_downstream,
                requested_release_step=requested_release_step,
                capacity_available=remaining_capacity_for_ramps
            )

            for ramp, accepted in ramp_acceptance.items():
                actual_release_step[ramp] = accepted

            if ramps_feeding_downstream:
                merge_diagnostics["normal_merge_remaining_capacity"][downstream_cell] = remaining_capacity_for_ramps
                merge_diagnostics["normal_merge_ramp_requests"][downstream_cell] = {
                    ramp: float(requested_release_step[ramp])
                    for ramp in ramps_feeding_downstream
                }
                merge_diagnostics["normal_merge_ramp_acceptance"][downstream_cell] = ramp_acceptance.copy()

        if 1.0 - beta <= 1e-12:
            total_leave = 0.0
        else:
            total_leave = q_out[cell] / (1.0 - beta)

        total_leave = min(
            total_leave,
            sending_total[cell]
        )

        split_exit_flow[cell] = (
            beta
            * total_leave
        )

    # 4. Internal inflow identities.
    for i in range(1, len(cells)):
        q_in[cells[i]] = q_out[cells[i - 1]]

    # 5. Terminal Cell 9 outflow.
    beta9 = float(exit_split_by_cell["Cell 9"])
    terminal_leave = sending_total["Cell 9"]

    q_out["Cell 9"] = (
        1.0
        - beta9
    ) * terminal_leave

    split_exit_flow["Cell 9"] = (
        beta9
        * terminal_leave
    )

    # 6. Mainline state update with accepted controlled ramp releases.
    controllable_onramp_in_step = build_controllable_onramp_in_from_actual_release(
        actual_release_step
    )

    for cell in cells:
        external_inflow = max(
            0.0,
            float(external_inflow_step[cell])
        )

        ramp_inflow = max(
            0.0,
            float(controllable_onramp_in_step[cell])
        )

        available_before_fixed_off = max(
            0.0,
            float(x_current[cell])
            + float(q_in[cell])
            + external_inflow
            + ramp_inflow
            - float(q_out[cell])
            - float(split_exit_flow[cell])
        )

        actual_fixed_f_out[cell] = min(
            max(
                0.0,
                float(fixed_outflow_step[cell])
            ),
            available_before_fixed_off
        )

        actual_f_out[cell] = (
            split_exit_flow[cell]
            + actual_fixed_f_out[cell]
        )

        x_next[cell] = (
            float(x_current[cell])
            + float(q_in[cell])
            + external_inflow
            + ramp_inflow
            - float(q_out[cell])
            - float(split_exit_flow[cell])
            - float(actual_fixed_f_out[cell])
        )

        x_next[cell] = max(
            0.0,
            x_next[cell]
        )

    return (
        x_next,
        q_out,
        q_in,
        sending_total,
        receiving,
        receiving_after_external,
        actual_f_out,
        split_exit_flow,
        actual_fixed_f_out,
        actual_release_step,
        controllable_onramp_in_step,
        upstream_boundary_queue_next,
        upstream_boundary_delay,
        merge_diagnostics
    )


def mainline_delay_one_step(
    x_now,
    x_next,
    q_out,
    actual_f_out,
    tt_ff_min,
    delta_t
):
    rows = []

    total_mainline_delay_raw = 0.0
    total_mainline_delay_clipped = 0.0

    for cell in cell_ids:
        if cell not in x_now:
            raise KeyError(f"{cell} missing from x_now")

        if cell not in x_next:
            raise KeyError(f"{cell} missing from x_next")

        if cell not in q_out:
            raise KeyError(f"{cell} missing from q_out")

        if cell not in actual_f_out:
            raise KeyError(f"{cell} missing from actual_f_out")

        if cell not in tt_ff_min:
            raise KeyError(f"{cell} missing from tt_ff_min")

        ttt = (
            (
                float(x_now[cell])
                + float(x_next[cell])
            )
            / 2.0
        ) * float(delta_t)

        ff_term = (
            float(q_out[cell])
            + float(actual_f_out[cell])
        ) * float(tt_ff_min[cell])

        delay_raw = (
            ttt
            - ff_term
        )

        delay_clipped = max(
            delay_raw,
            0.0
        )

        total_mainline_delay_raw += delay_raw
        total_mainline_delay_clipped += delay_clipped

        rows.append({
            "cell": cell,
            "x_now": x_now[cell],
            "x_next": x_next[cell],
            "q_out": q_out[cell],
            "actual_f_out": actual_f_out[cell],
            "TTT_veh_min": ttt,
            "free_flow_component": ff_term,
            "delay_raw": delay_raw,
            "delay_clipped": delay_clipped,
            "mainline_delay_veh_min": delay_clipped,
        })

    mainline_delay_df = pd.DataFrame(rows)

    return (
        mainline_delay_df,
        total_mainline_delay_raw,
        total_mainline_delay_clipped
    )


# LOCAL RAMP DELAY CALCULATION FOR ONE CTM STEP
def ramp_delay_with_cap(
    R_current,
    R_next,
    B_current,
    B_next,
    ramp_arrival_step,
    commanded_release_step,
    requested_release_step,
    actual_release_step,
    delta_t
):
    rows = []
    total_local_delay = 0.0

    for ramp in ramp_ids:
        required_dicts = {
            "R_current": R_current,
            "R_next": R_next,
            "B_current": B_current,
            "B_next": B_next,
            "ramp_arrival_step": ramp_arrival_step,
            "commanded_release_step": commanded_release_step,
            "requested_release_step": requested_release_step,
            "actual_release_step": actual_release_step,
        }

        for name, dictionary in required_dicts.items():
            if ramp not in dictionary:
                raise KeyError(f"{ramp} missing from {name}")

        waiting_current = (
            float(R_current[ramp])
            + float(B_current.get(ramp, 0.0))
        )

        waiting_next = (
            float(R_next[ramp])
            + float(B_next.get(ramp, 0.0))
        )

        waiting_avg = (waiting_current + waiting_next) / 2.0
        local_delay = waiting_avg * delta_t

        total_local_delay += local_delay

        rows.append({
            "ramp": ramp,
            "R_current": R_current[ramp],
            "B_current": B_current.get(ramp, 0.0),
            "arrival": ramp_arrival_step[ramp],
            "commanded_release": commanded_release_step[ramp],
            "requested_release": requested_release_step[ramp],
            "actual_release": actual_release_step[ramp],
            "R_next": R_next[ramp],
            "B_next": B_next.get(ramp, 0.0),
            "waiting_current": waiting_current,
            "waiting_next": waiting_next,
            "waiting_avg": waiting_avg,
            "local_delay_veh_min": local_delay,
        })

    ramp_delay_df = pd.DataFrame(rows)

    return ramp_delay_df, total_local_delay


# OFFICIAL 480-STEP STATE-BASED CTM BENCHMARK SIMULATION
def simulate_state_based_benchmark_480_steps(
    num_steps,
    mainline_initial_state,
    ramp_queue_0,
    q_in_boundary_series,
    commanded_release_series,
    ramp_arrival_series,
    external_inflow_series,
    fixed_outflow_series,
    inflow_capacity,
    outflow_capacity,
    physical_capacity,
    safe_threshold_capacity,
    ramp_name_map,
    ramp_max_queue_named,
    ramp_max_queue_by_u,
    tt_ff_min,
    delta_t,
    gamma,
    lambda_1,
    lambda_2,
    lambda_3,
    lambda_4,
    movement_factor_by_cell,
    wave_speed_ratio_by_cell,
    exit_split_by_cell,
    external_queue_0=None,
    use_clipped_mainline_delay=True
):
    # 0. Sanity checks.
    assert num_steps == 480, (
        f"Official two-hour benchmark must have 480 steps, got {num_steps}."
    )

    assert list(mainline_initial_state.keys()) == cell_ids
    assert list(inflow_capacity.keys()) == cell_ids
    assert list(outflow_capacity.keys()) == cell_ids
    assert list(physical_capacity.keys()) == cell_ids
    assert list(safe_threshold_capacity.keys()) == cell_ids
    assert list(tt_ff_min.keys()) == cell_ids
    assert list(movement_factor_by_cell.keys()) == cell_ids
    assert list(wave_speed_ratio_by_cell.keys()) == cell_ids
    assert list(exit_split_by_cell.keys()) == cell_ids

    assert set(ramp_queue_0.keys()) == set(ramp_ids)
    assert set(ramp_max_queue_by_u.keys()) == set(ramp_ids)
    assert set(ramp_name_map.keys()) == set(ramp_ids)

    assert merge_ramp_id == "u_avila"
    assert ramp_cell_map[merge_ramp_id] == merge_ramp_cell
    assert merge_ramp_id not in generic_ramp_cell_map

    assert len(q_in_boundary_series) == num_steps
    assert len(external_inflow_series) == num_steps
    assert len(fixed_outflow_series) == num_steps

    for ramp in ramp_ids:
        assert len(commanded_release_series[ramp]) == num_steps
        assert len(ramp_arrival_series[ramp]) == num_steps

    for step in range(num_steps):
        assert list(external_inflow_series[step].keys()) == cell_ids
        assert list(fixed_outflow_series[step].keys()) == cell_ids

    # 1. Initial states.
    x_current = mainline_initial_state.copy()
    R_current = ramp_queue_0.copy()
    upstream_boundary_queue_current = 0.0

    if external_queue_0 is None:
        B_current = {
            ramp: 0.0
            for ramp in ramp_ids
        }
    else:
        assert set(external_queue_0.keys()) == set(ramp_ids)
        B_current = external_queue_0.copy()

    # 2. History container.
    history = {
        "step": [],
        "x": [],
        "R": [],
        "B": [],
        "q_in": [],
        "q_out": [],
        "external_inflow": [],
        "fixed_outflow": [],
        "actual_f_out": [],
        "split_exit_flow": [],
        "actual_fixed_f_out": [],
        "commanded_release": [],
        "requested_release": [],
        "actual_release": [],
        "ramp_arrival": [],
        "ramp_available_demand": [],
        "spillback": [],
        "controllable_onramp_in": [],
        "sending": [],
        "receiving": [],
        "receiving_after_external": [],
        "merge_diagnostics": [],

        # Avila diagnostics
        "avila_available_demand": [],
        "avila_commanded_release": [],
        "avila_release_request": [],
        "avila_release_demand": [],
        "avila_accepted": [],

        "upstream_boundary_queue": [],
        "upstream_boundary_delay": [],
        "mainline_delay": [],
        "mainline_delay_raw": [],
        "mainline_delay_clipped": [],
        "local_delay": [],
        "fairness_penalty": [],
        "doorway_penalty": [],
        "safe_penalty": [],
        "physical_penalty": [],
        "spillback_penalty": [],
        "capacity_penalty": [],
        "total_objective": [],
    }

    # 3. Simulation loop.
    for step in range(num_steps):
        q_in_boundary_step = float(
            q_in_boundary_series[step]
        )

        commanded_release_step = {
            ramp: float(commanded_release_series[ramp][step])
            for ramp in ramp_ids
        }

        ramp_arrival_step = {
            ramp: float(ramp_arrival_series[ramp][step])
            for ramp in ramp_ids
        }

        external_inflow_step = external_inflow_series[step]
        fixed_outflow_step = fixed_outflow_series[step]

        (
            available_demand_step,
            requested_release_step,
        ) = ramp_requested_release_one_step(
            R_current=R_current,
            B_current=B_current,
            ramp_arrival_step=ramp_arrival_step,
            commanded_release_step=commanded_release_step
        )

        (
            x_next,
            q_out,
            q_in,
            sending,
            receiving,
            receiving_after_external,
            actual_f_out,
            split_exit_flow,
            actual_fixed_f_out,
            actual_release_step,
            controllable_onramp_in_step,
            upstream_boundary_queue_next,
            upstream_boundary_delay,
            merge_diagnostics,
        ) = ctm_15sec_step(
            x_current=x_current,
            q_in_boundary_step=q_in_boundary_step,
            external_inflow_step=external_inflow_step,
            fixed_outflow_step=fixed_outflow_step,
            requested_release_step=requested_release_step,
            inflow_capacity=inflow_capacity,
            outflow_capacity=outflow_capacity,
            physical_capacity=physical_capacity,
            movement_factor_by_cell=movement_factor_by_cell,
            wave_speed_ratio_by_cell=wave_speed_ratio_by_cell,
            upstream_boundary_queue=upstream_boundary_queue_current,
            exit_split_by_cell=exit_split_by_cell,
            merge_priority=MERGE_PRIORITY
        )

        (
            R_next,
            B_next,
            spillback_by_ramp,
        ) = ramp_next_queue_after_actual_release(
            available_demand_step=available_demand_step,
            actual_release_step=actual_release_step,
            ramp_max_queue_by_u=ramp_max_queue_by_u
        )

        for ramp in ramp_ids:
            if actual_release_step[ramp] - requested_release_step[ramp] > 1e-9:
                raise AssertionError(
                    f"Actual release exceeds requested release for {ramp}."
                )

        # Local ramp delay.
        _, total_local_delay = ramp_delay_with_cap(
            R_current=R_current,
            R_next=R_next,
            B_current=B_current,
            B_next=B_next,
            ramp_arrival_step=ramp_arrival_step,
            commanded_release_step=commanded_release_step,
            requested_release_step=requested_release_step,
            actual_release_step=actual_release_step,
            delta_t=delta_t
        )

        # Fairness penalty.
        _, _, L_fair = fairness_penalty_one_step(
            R_next=R_next,
            ramp_name_map=ramp_name_map,
            ramp_max_queue_named=ramp_max_queue_named,
            gamma=gamma
        )

        # State-based mainline delay.
        (
            _,
            total_mainline_delay_raw,
            total_mainline_delay_clipped,
        ) = mainline_delay_one_step(
            x_now=x_current,
            x_next=x_next,
            q_out=q_out,
            actual_f_out=actual_f_out,
            tt_ff_min=tt_ff_min,
            delta_t=delta_t
        )

        if use_clipped_mainline_delay:
            total_mainline_delay = (
                total_mainline_delay_clipped
                + upstream_boundary_delay
            )
        else:
            total_mainline_delay = (
                total_mainline_delay_raw
                + upstream_boundary_delay
            )

        # Capacity penalties.
        capacity_info = capacity_penalty_one_step(
            q_in=q_in,
            external_inflow_step=external_inflow_step,
            controllable_onramp_in_step=controllable_onramp_in_step,
            x_next=x_next,
            inflow_capacity=inflow_capacity,
            safe_threshold_capacity=safe_threshold_capacity,
            physical_capacity=physical_capacity,
            spillback_by_ramp=spillback_by_ramp,
            lambda_1=lambda_1,
            lambda_2=lambda_2,
            lambda_3=lambda_3,
            lambda_4=lambda_4
        )

        # Total objective.
        total_objective = (
            total_mainline_delay
            + total_local_delay
            + L_fair
            + capacity_info["total_capacity_penalty"]
        )

        # Store results.
        history["step"].append(step)
        history["x"].append(x_next.copy())
        history["R"].append(R_next.copy())
        history["B"].append(B_next.copy())
        history["q_in"].append(q_in.copy())
        history["q_out"].append(q_out.copy())
        history["external_inflow"].append(external_inflow_step.copy())
        history["fixed_outflow"].append(fixed_outflow_step.copy())
        history["actual_f_out"].append(actual_f_out.copy())
        history["split_exit_flow"].append(split_exit_flow.copy())
        history["actual_fixed_f_out"].append(actual_fixed_f_out.copy())
        history["commanded_release"].append(commanded_release_step.copy())
        history["requested_release"].append(requested_release_step.copy())
        history["actual_release"].append(actual_release_step.copy())
        history["ramp_arrival"].append(ramp_arrival_step.copy())
        history["ramp_available_demand"].append(available_demand_step.copy())
        history["spillback"].append(spillback_by_ramp.copy())
        history["controllable_onramp_in"].append(controllable_onramp_in_step.copy())
        history["sending"].append(sending.copy())
        history["receiving"].append(receiving.copy())
        history["receiving_after_external"].append(receiving_after_external.copy())
        history["merge_diagnostics"].append(merge_diagnostics.copy())

        history["avila_available_demand"].append(
            float(available_demand_step[merge_ramp_id])
        )

        history["avila_commanded_release"].append(
            float(commanded_release_step[merge_ramp_id])
        )

        history["avila_release_request"].append(
            float(requested_release_step[merge_ramp_id])
        )

        history["avila_release_demand"].append(
            float(requested_release_step[merge_ramp_id])
        )

        history["avila_accepted"].append(
            float(actual_release_step[merge_ramp_id])
        )

        history["upstream_boundary_queue"].append(
            upstream_boundary_queue_next
        )

        history["upstream_boundary_delay"].append(
            upstream_boundary_delay
        )

        history["mainline_delay"].append(
            total_mainline_delay
        )

        history["mainline_delay_raw"].append(
            total_mainline_delay_raw
        )

        history["mainline_delay_clipped"].append(
            total_mainline_delay_clipped
        )

        history["local_delay"].append(
            total_local_delay
        )

        history["fairness_penalty"].append(
            L_fair
        )

        history["doorway_penalty"].append(
            capacity_info["total_doorway_penalty"]
        )

        history["safe_penalty"].append(
            capacity_info["total_safe_threshold_penalty"]
        )

        history["physical_penalty"].append(
            capacity_info["total_physical_capacity_penalty"]
        )

        history["spillback_penalty"].append(
            capacity_info["total_spillback_penalty"]
        )

        history["capacity_penalty"].append(
            capacity_info["total_capacity_penalty"]
        )

        history["total_objective"].append(
            total_objective
        )

        # Move to next step.
        x_current = x_next.copy()
        R_current = R_next.copy()
        B_current = B_next.copy()
        upstream_boundary_queue_current = upstream_boundary_queue_next

    # 4. Final states.
    history["R_final"] = R_current.copy()
    history["B_final"] = B_current.copy()
    history["x_final"] = x_current.copy()
    history["upstream_boundary_queue_final"] = upstream_boundary_queue_current

    assert len(history["step"]) == num_steps

    return history



# Run the official 480-step benchmark from the exported inputs and check it.
official_benchmark_history = simulate_state_based_benchmark_480_steps(
    num_steps=num_steps,
    mainline_initial_state=get_input("mainline_initial_state"),
    ramp_queue_0=get_input("ramp_queue_0"),
    q_in_boundary_series=get_input("q_in_boundary_series"),
    commanded_release_series=get_input("commanded_release_series"),
    ramp_arrival_series=get_input("ramp_arrival_series"),
    external_inflow_series=get_input("external_inflow_series"),
    fixed_outflow_series=get_input("fixed_outflow_series"),
    inflow_capacity=get_input("inflow_capacity"),
    outflow_capacity=get_input("outflow_capacity"),
    physical_capacity=get_input("physical_capacity"),
    safe_threshold_capacity=get_input("safe_threshold_capacity"),
    ramp_name_map=get_input("ramp_name_map"),
    ramp_max_queue_named=get_input("ramp_max_queue_named"),
    ramp_max_queue_by_u=get_input("ramp_max_queue_by_u"),
    tt_ff_min=get_input("tt_ff_min"),
    delta_t=delta_t,
    gamma=gamma,
    lambda_1=lambda_1,
    lambda_2=lambda_2,
    lambda_3=lambda_3,
    lambda_4=lambda_4,
    movement_factor_by_cell=get_input("movement_factor_by_cell"),
    wave_speed_ratio_by_cell=get_input("wave_speed_ratio_by_cell"),
    exit_split_by_cell=get_input("exit_split_by_cell"),
    external_queue_0=get_input("external_queue_0"),
    use_clipped_mainline_delay=use_clipped_mainline_delay,
)

# Aggregate totals exactly as Benchmark_calculation.ipynb does.
reproduced_totals = {
    "mainline_delay": sum(official_benchmark_history["mainline_delay"]),
    "mainline_delay_raw": sum(official_benchmark_history["mainline_delay_raw"]),
    "mainline_delay_clipped": sum(official_benchmark_history["mainline_delay_clipped"]),
    "upstream_boundary_delay": sum(official_benchmark_history["upstream_boundary_delay"]),
    "local_delay": sum(official_benchmark_history["local_delay"]),
    "fairness_penalty": sum(official_benchmark_history["fairness_penalty"]),
    "doorway_penalty": sum(official_benchmark_history["doorway_penalty"]),
    "safe_penalty": sum(official_benchmark_history["safe_penalty"]),
    "physical_penalty": sum(official_benchmark_history["physical_penalty"]),
    "spillback_penalty": sum(official_benchmark_history["spillback_penalty"]),
}
reproduced_totals["capacity_penalty"] = (
    reproduced_totals["doorway_penalty"]
    + reproduced_totals["safe_penalty"]
    + reproduced_totals["physical_penalty"]
    + reproduced_totals["spillback_penalty"]
)
reproduced_totals["raw_objective"] = (
    reproduced_totals["mainline_delay"]
    + reproduced_totals["local_delay"]
    + reproduced_totals["fairness_penalty"]
    + reproduced_totals["capacity_penalty"]
)


print("Benchmark_calculation.py reproduction check (vs exported official_totals)")

comparison_rows = []
max_abs_diff = 0.0
for key in reproduced_totals:
    rep = float(reproduced_totals[key])
    off = float(official_totals[key]) if key in official_totals else float("nan")
    diff = rep - off
    if off == off:
        max_abs_diff = max(max_abs_diff, abs(diff))
    comparison_rows.append({"metric": key, "reproduced": rep, "official": off, "diff": diff})
    print("  %-26s reproduced=%15.6f  official=%15.6f  diff=%.3e" % (key, rep, off, diff))

print("max abs totals diff vs official:", max_abs_diff)
if max_abs_diff >= 1e-6:
    raise AssertionError("Benchmark_calculation.py does NOT reproduce the exported official benchmark.")
print("PASS: totals reproduce the official benchmark (receiving-aware CTM, LINEAR spillback).")

# Ramp mass conservation.
_R0 = get_input("ramp_queue_0")
_B0 = get_input("external_queue_0")
_arr = get_input("ramp_arrival_series")
total_initial = sum(float(_R0.get(r, 0.0)) + float(_B0.get(r, 0.0)) for r in ramp_ids)
total_arrivals = sum(float(_arr[r][k]) for r in ramp_ids for k in range(num_steps))
total_released = sum(float(official_benchmark_history["actual_release"][k][r]) for r in ramp_ids for k in range(num_steps))
final_R = sum(float(official_benchmark_history["R_final"][r]) for r in ramp_ids)
final_B = sum(float(official_benchmark_history["B_final"][r]) for r in ramp_ids)
ramp_mass_residual = total_initial + total_arrivals - total_released - final_R - final_B
print("ramp mass residual:", ramp_mass_residual)
if abs(ramp_mass_residual) >= 1e-6:
    raise AssertionError("Ramp mass conservation failed.")
print("PASS: ramp mass conserved.")


print("Reproduced raw objective:", round(reproduced_totals["raw_objective"], 6))
print("MERGE_PRIORITY:", MERGE_PRIORITY, "| arrival_multiplier:", arrival_multiplier)
