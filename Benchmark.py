"""
Official 9-cell / 15-second CTM benchmark reproduction script.

This script reproduces the final state-based CTM benchmark from
shared_benchmark_inputs.pkl exported by Benchmark_calculation.ipynb.

It is intentionally written as a standalone .py checker:
- loads the exported source-of-truth inputs,
- re-runs the official 480-step benchmark,
- checks totals against official notebook values,
- checks ramp mass conservation.

Important model features included:
- 9 CTM cells, 15-second time step, 480 steps,
- 4 ramps: u_4th, u_price, u_mattie, u_avila,
- Avila enters Cell 9 only through the special merge,
- Avila release request is capped by historical observed release,
- 30% Avila merge priority is applied inside ctm_15sec_step,
- hidden exit split fractions are applied inside CTM links,
- persistent physical ramp queues R and external spillback queues B.
"""

from __future__ import annotations

from pathlib import Path
import pickle
from typing import Any

import pandas as pd


# Load shared benchmark inputs
SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_INPUTS_PATH = SCRIPT_DIR / "shared_benchmark_inputs.pkl"

if not SHARED_INPUTS_PATH.exists():
    raise FileNotFoundError(
        "shared_benchmark_inputs.pkl was not found next to this script. "
        "Run the export cell in Benchmark_calculation.ipynb first."
    )

with open(SHARED_INPUTS_PATH, "rb") as file:
    shared: dict[str, Any] = pickle.load(file)


def get_input(name: str) -> Any:
    if name not in shared:
        raise KeyError(f"{name} was not found in shared_benchmark_inputs.pkl")
    return shared[name]


def get_optional_input(name: str, default_value: Any) -> Any:
    return shared[name] if name in shared else default_value


def sorted_cell_ids_from(keys) -> list[str]:
    return sorted(keys, key=lambda name: int(str(name).split()[1]))


# Source-of-truth variables from notebook export
official_totals = get_input("official_totals")
official_service_metrics = get_optional_input("official_service_metrics", {})

num_steps = int(get_input("num_steps"))
delta_t = float(get_input("delta_t"))
arrival_multiplier = float(get_optional_input("arrival_multiplier", 1.0))
use_clipped_mainline_delay = bool(
    get_optional_input("use_clipped_mainline_delay", True)
)

# Objective weights
gamma = float(get_input("gamma"))
lambda_1 = float(get_input("lambda_1"))
lambda_2 = float(get_input("lambda_2"))
lambda_3 = float(get_input("lambda_3"))
lambda_4 = float(get_input("lambda_4"))

# Initial states
mainline_initial_state = get_input("mainline_initial_state")
ramp_queue_0 = get_input("ramp_queue_0")
external_queue_0 = get_input("external_queue_0")

# IDs and mapping
cell_ids = sorted_cell_ids_from(mainline_initial_state.keys())
ramp_ids = list(get_input("ramp_ids"))
ramp_cell_map = get_input("ramp_cell_map")
generic_ramp_cell_map = get_input("generic_ramp_cell_map")
merge_ramp_id = get_input("merge_ramp_id")
merge_ramp_cell = get_input("merge_ramp_cell")
MERGE_PRIORITY = float(get_input("MERGE_PRIORITY"))

# Time series
q_in_boundary_series = get_input("q_in_boundary_series")
observed_release_series = get_input("observed_release_series")
ramp_arrival_series = get_input("ramp_arrival_series")
u_in_series = get_input("u_in_series")
f_out_series = get_input("f_out_series")
residual_inflow_series = get_input("residual_inflow_series")
residual_outflow_series = get_input("residual_outflow_series")

# CTM parameters
inflow_capacity = get_input("inflow_capacity")
outflow_capacity = get_input("outflow_capacity")
physical_capacity = get_input("physical_capacity")
safe_threshold_capacity = get_input("safe_threshold_capacity")
movement_factor_by_cell = get_input("movement_factor_by_cell")
wave_speed_ratio_by_cell = get_input("wave_speed_ratio_by_cell")
exit_split_by_cell = get_input("exit_split_by_cell")
undetected_entry_per_15sec_by_cell = get_input(
    "undetected_entry_per_15sec_by_cell"
)
tt_ff_min = get_input("tt_ff_min")

# Ramp metadata
ramp_name_map = get_input("ramp_name_map")
ramp_max_queue_named = get_input("ramp_max_queue_named")
ramp_max_queue_by_u = get_input("ramp_max_queue_by_u")



# Validation of exported setup

assert num_steps == 480, f"Expected 480 CTM steps, got {num_steps}."
assert abs(delta_t - 0.25) < 1e-12, f"Expected 15-sec delta_t=0.25, got {delta_t}."
assert cell_ids == [f"Cell {i}" for i in range(1, 10)], cell_ids
assert len(ramp_ids) == 4, ramp_ids
assert merge_ramp_id == "u_avila", merge_ramp_id
assert merge_ramp_cell == "Cell 9", merge_ramp_cell
assert merge_ramp_id not in generic_ramp_cell_map
assert set(ramp_ids) == set(ramp_queue_0.keys())
assert set(ramp_ids) == set(external_queue_0.keys())

for dictionary_name, dictionary in [
    ("inflow_capacity", inflow_capacity),
    ("outflow_capacity", outflow_capacity),
    ("physical_capacity", physical_capacity),
    ("safe_threshold_capacity", safe_threshold_capacity),
    ("movement_factor_by_cell", movement_factor_by_cell),
    ("wave_speed_ratio_by_cell", wave_speed_ratio_by_cell),
    ("exit_split_by_cell", exit_split_by_cell),
    ("tt_ff_min", tt_ff_min),
]:
    assert sorted_cell_ids_from(dictionary.keys()) == cell_ids, dictionary_name


#
# Helper functions

def ramp_next_queue_with_spillback(
    R_current: dict[str, float],
    B_current: dict[str, float],
    ramp_arrival_step: dict[str, float],
    commanded_release_step: dict[str, float],
    ramp_max_queue_by_u: dict[str, float],
):
    """Update physical ramp queue R and external spillback queue B."""

    R_next = {}
    B_next = {}
    spillback_by_ramp = {}
    actual_release_step = {}

    for ramp in R_current:
        if ramp not in ramp_arrival_step:
            raise KeyError(f"{ramp} missing from ramp_arrival_step")
        if ramp not in commanded_release_step:
            raise KeyError(f"{ramp} missing from commanded_release_step")
        if ramp not in ramp_max_queue_by_u:
            raise KeyError(f"{ramp} missing from ramp_max_queue_by_u")

        R_now = float(R_current[ramp])
        B_now = float(B_current.get(ramp, 0.0))
        arrival = float(ramp_arrival_step[ramp])
        commanded_release = float(commanded_release_step[ramp])
        R_max = float(ramp_max_queue_by_u[ramp])

        if R_max <= 0:
            raise ValueError(f"Invalid R_max for {ramp}: {R_max}")

        available = max(0.0, R_now) + max(0.0, B_now) + max(0.0, arrival)
        actual_release = min(max(0.0, commanded_release), available)
        waiting_after_release = max(0.0, available - actual_release)

        R_next[ramp] = min(waiting_after_release, R_max)
        B_next[ramp] = max(0.0, waiting_after_release - R_max)
        spillback_by_ramp[ramp] = B_next[ramp]
        actual_release_step[ramp] = actual_release

    return R_next, B_next, spillback_by_ramp, actual_release_step



def fairness_penalty_one_step(
    R_next: dict[str, float],
    ramp_name_map: dict[str, str],
    ramp_max_queue_named: dict[str, float],
    gamma: float,
):
    """Pairwise ramp queue fairness penalty using capped physical queue stress."""

    stress_dict = {}

    for ramp, R_t in R_next.items():
        ramp_name = ramp_name_map[ramp]
        R_max_i = float(ramp_max_queue_named[ramp_name])

        if R_max_i <= 0:
            raise ValueError(f"Invalid R_max for {ramp_name}: {R_max_i}")

        raw_stress = float(R_t) / R_max_i
        capped_stress = min(max(raw_stress, 0.0), 1.0)
        stress_dict[ramp_name] = capped_stress

    ramp_names = list(stress_dict.keys())
    fairness_sum = 0.0

    for i in range(len(ramp_names)):
        for j in range(i + 1, len(ramp_names)):
            phi_i = stress_dict[ramp_names[i]]
            phi_j = stress_dict[ramp_names[j]]
            fairness_sum += (phi_i - phi_j) ** 2

    L_fair = gamma * fairness_sum
    return stress_dict, fairness_sum, L_fair



def ramp_delay_with_cap(
    R_current: dict[str, float],
    R_next: dict[str, float],
    B_current: dict[str, float],
    B_next: dict[str, float],
    ramp_arrival_step: dict[str, float],
    commanded_release_step: dict[str, float],
    actual_release_step: dict[str, float],
    delta_t: float,
):
    """Local ramp delay from physical queue plus external spillback queue."""

    rows = []
    total_local_delay = 0.0

    for ramp in ramp_ids:
        for name, dictionary in {
            "R_current": R_current,
            "R_next": R_next,
            "ramp_arrival_step": ramp_arrival_step,
            "commanded_release_step": commanded_release_step,
            "actual_release_step": actual_release_step,
        }.items():
            if ramp not in dictionary:
                raise KeyError(f"{ramp} missing from {name}")

        waiting_current = float(R_current[ramp]) + float(B_current.get(ramp, 0.0))
        waiting_next = float(R_next[ramp]) + float(B_next.get(ramp, 0.0))
        waiting_avg = (waiting_current + waiting_next) / 2.0
        local_delay = waiting_avg * delta_t
        total_local_delay += local_delay

        rows.append(
            {
                "ramp": ramp,
                "R_current": R_current[ramp],
                "B_current": B_current.get(ramp, 0.0),
                "arrival": ramp_arrival_step[ramp],
                "commanded_release": commanded_release_step[ramp],
                "actual_release": actual_release_step[ramp],
                "R_next": R_next[ramp],
                "B_next": B_next.get(ramp, 0.0),
                "waiting_current": waiting_current,
                "waiting_next": waiting_next,
                "waiting_avg": waiting_avg,
                "local_delay_veh_min": local_delay,
            }
        )

    return pd.DataFrame(rows), total_local_delay



def build_controllable_onramp_in_from_actual_release(
    actual_release_step: dict[str, float]
):
    """
    Build controllable ramp inflow by cell for the capacity penalty.

    This includes Avila because actual_release_step['u_avila'] is already the
    merge-accepted Avila release. This dictionary is NOT used to update the
    mainline state; the CTM state update gets Avila through avila_accepted.
    """

    controllable_onramp_in_step = {cell: 0.0 for cell in cell_ids}

    for ramp in ramp_ids:
        if ramp not in actual_release_step:
            raise KeyError(f"{ramp} missing from actual_release_step")

        cell = ramp_cell_map[ramp]
        controllable_onramp_in_step[cell] += float(actual_release_step[ramp])

    return controllable_onramp_in_step



def ctm_15sec_step(
    x_current: dict[str, float],
    q_in_boundary_step: float,
    u_in_step: dict[str, float],
    f_out_step: dict[str, float],
    avila_release_demand: float,
    inflow_capacity: dict[str, float],
    outflow_capacity: dict[str, float],
    physical_capacity: dict[str, float],
    movement_factor_by_cell: dict[str, float],
    wave_speed_ratio_by_cell: dict[str, float],
    upstream_boundary_queue: float = 0.0,
    exit_split_by_cell: dict[str, float] | None = None,
    merge_priority: float | None = None,
):
    """Official 15-second CTM step with hidden exits and Avila merge."""

    cells = cell_ids

    if exit_split_by_cell is None:
        exit_split_by_cell = {cell: 0.0 for cell in cells}

    if merge_priority is None:
        merge_priority = MERGE_PRIORITY

    assert list(exit_split_by_cell.keys()) == cells

    sending_total = {}
    receiving = {}
    q_out = {}
    q_in = {}
    split_exit_flow = {}
    actual_fixed_f_out = {}
    actual_f_out = {}
    x_next = {}

    # 1. Sending and receiving
    for cell in cells:
        beta = float(exit_split_by_cell[cell])
        if beta < 0.0 or beta >= 1.0:
            raise ValueError(
                f"exit_split_by_cell[{cell}] must be in [0, 1). Got {beta}."
            )

        sending_total[cell] = min(
            float(movement_factor_by_cell[cell]) * float(x_current[cell]),
            float(outflow_capacity[cell]),
        )

        available_storage = max(
            0.0,
            float(physical_capacity[cell]) - float(x_current[cell]),
        )

        receiving[cell] = max(
            0.0,
            min(
                float(inflow_capacity[cell]),
                float(wave_speed_ratio_by_cell[cell]) * available_storage,
            ),
        )

    # 2. Mainline links except Cell 8 -> Cell 9 merge
    for i, cell in enumerate(cells):
        beta = float(exit_split_by_cell[cell])

        if cell == "Cell 8":
            continue

        if i < len(cells) - 1:
            downstream_cell = cells[i + 1]

            if 1.0 - beta <= 1e-12:
                total_leave = 0.0
            else:
                total_leave = min(
                    sending_total[cell],
                    receiving[downstream_cell] / (1.0 - beta),
                )

            q_out[cell] = (1.0 - beta) * total_leave
            split_exit_flow[cell] = beta * total_leave

        else:
            # Last modeled cell exits the corridor.
            total_leave = sending_total[cell]
            q_out[cell] = (1.0 - beta) * total_leave
            split_exit_flow[cell] = beta * total_leave

    # 3. Avila merge at Cell 9 entrance
    beta8 = float(exit_split_by_cell["Cell 8"])
    if beta8 < 0.0 or beta8 >= 1.0:
        raise ValueError(f"exit_split_by_cell['Cell 8'] must be in [0, 1). Got {beta8}.")

    cell8_total_sending = sending_total["Cell 8"]
    cell8_mainline_demand = (1.0 - beta8) * cell8_total_sending
    R9 = receiving["Cell 9"]
    avila_demand = max(0.0, float(avila_release_demand))

    avila_capacity_share = max(
        float(merge_priority) * R9,
        R9 - cell8_mainline_demand,
    )
    avila_capacity_share = max(0.0, min(R9, avila_capacity_share))

    avila_accepted = min(avila_demand, avila_capacity_share)
    cell8_mainline_accepted = min(
        cell8_mainline_demand,
        max(0.0, R9 - avila_accepted),
    )

    q_out["Cell 8"] = cell8_mainline_accepted

    if 1.0 - beta8 <= 1e-12:
        cell8_total_leave = 0.0
    else:
        cell8_total_leave = cell8_mainline_accepted / (1.0 - beta8)

    cell8_total_leave = min(cell8_total_leave, cell8_total_sending)
    split_exit_flow["Cell 8"] = beta8 * cell8_total_leave

    # 4. Boundary inflow with upstream boundary queue
    boundary_demand = float(upstream_boundary_queue) + float(q_in_boundary_step)
    q_in["Cell 1"] = min(boundary_demand, receiving["Cell 1"])
    upstream_boundary_queue_next = boundary_demand - q_in["Cell 1"]

    upstream_boundary_delay = (
        (float(upstream_boundary_queue) + float(upstream_boundary_queue_next))
        / 2.0
    ) * delta_t

    # 5. Internal mainline inflows
    for i in range(1, len(cells)):
        current_cell = cells[i]
        upstream_cell = cells[i - 1]
        q_in[current_cell] = q_out[upstream_cell]

    # 6. Cell state update
    for cell in cells:
        external_inflow = float(u_in_step[cell])

        if cell == merge_ramp_cell:
            external_inflow += avila_accepted

        available_before_fixed_off = max(
            0.0,
            float(x_current[cell])
            + float(q_in[cell])
            + external_inflow
            - float(q_out[cell])
            - float(split_exit_flow[cell]),
        )

        actual_fixed_f_out[cell] = min(
            max(0.0, float(f_out_step[cell])),
            available_before_fixed_off,
        )

        actual_f_out[cell] = split_exit_flow[cell] + actual_fixed_f_out[cell]

        x_next[cell] = (
            float(x_current[cell])
            + float(q_in[cell])
            + external_inflow
            - float(q_out[cell])
            - float(split_exit_flow[cell])
            - float(actual_fixed_f_out[cell])
        )
        x_next[cell] = max(0.0, x_next[cell])

    return (
        x_next,
        q_out,
        q_in,
        sending_total,
        receiving,
        actual_f_out,
        avila_accepted,
        upstream_boundary_queue_next,
        upstream_boundary_delay,
    )



def mainline_delay_one_step(
    x_now: dict[str, float],
    x_next: dict[str, float],
    q_out: dict[str, float],
    actual_f_out: dict[str, float],
    tt_ff_min: dict[str, float],
    delta_t: float,
):
    """State-based mainline delay for one CTM step."""

    rows = []
    total_mainline_delay_raw = 0.0
    total_mainline_delay_clipped = 0.0

    for cell in cell_ids:
        for name, dictionary in {
            "x_now": x_now,
            "x_next": x_next,
            "q_out": q_out,
            "actual_f_out": actual_f_out,
            "tt_ff_min": tt_ff_min,
        }.items():
            if cell not in dictionary:
                raise KeyError(f"{cell} missing from {name}")

        ttt = ((float(x_now[cell]) + float(x_next[cell])) / 2.0) * float(delta_t)
        ff_term = (
            float(q_out[cell]) + float(actual_f_out[cell])
        ) * float(tt_ff_min[cell])
        delay_raw = ttt - ff_term
        delay_clipped = max(delay_raw, 0.0)

        total_mainline_delay_raw += delay_raw
        total_mainline_delay_clipped += delay_clipped

        rows.append(
            {
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
            }
        )

    return pd.DataFrame(rows), total_mainline_delay_raw, total_mainline_delay_clipped



def capacity_penalty_one_step(
    q_in: dict[str, float],
    u_in_step: dict[str, float],
    controllable_onramp_in_step: dict[str, float],
    x_next: dict[str, float],
    inflow_capacity: dict[str, float],
    safe_threshold_capacity: dict[str, float],
    physical_capacity: dict[str, float],
    spillback_by_ramp: dict[str, float],
    lambda_1: float,
    lambda_2: float,
    lambda_3: float,
    lambda_4: float,
):
    """Capacity penalty components for one CTM step."""

    doorway_penalty_by_cell = {}
    safe_threshold_penalty_by_cell = {}
    physical_capacity_penalty_by_cell = {}
    spillback_penalty_by_ramp = {}

    total_doorway_penalty = 0.0
    total_safe_threshold_penalty = 0.0
    total_physical_capacity_penalty = 0.0
    total_spillback_penalty = 0.0

    for cell in cell_ids:
        doorway_demand_pressure = float(q_in.get(cell, 0.0)) + float(
            controllable_onramp_in_step.get(cell, 0.0)
        )
        doorway_excess = max(0.0, doorway_demand_pressure - float(inflow_capacity[cell]))
        doorway_penalty = lambda_1 * doorway_excess**2
        doorway_penalty_by_cell[cell] = doorway_penalty
        total_doorway_penalty += doorway_penalty

        safe_excess = max(0.0, float(x_next[cell]) - float(safe_threshold_capacity[cell]))
        safe_penalty = lambda_2 * safe_excess**2
        safe_threshold_penalty_by_cell[cell] = safe_penalty
        total_safe_threshold_penalty += safe_penalty

        physical_excess = max(0.0, float(x_next[cell]) - float(physical_capacity[cell]))
        physical_penalty = lambda_3 * physical_excess**2
        physical_capacity_penalty_by_cell[cell] = physical_penalty
        total_physical_capacity_penalty += physical_penalty

    for ramp in ramp_ids:
        spillback_excess = max(0.0, float(spillback_by_ramp.get(ramp, 0.0)))
        spillback_penalty = lambda_4 * spillback_excess**2
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


# Official benchmark simulation
def simulate_state_based_benchmark_480_steps():
    """Re-run the official 480-step state-based benchmark."""

    # Sanity checks
    assert len(q_in_boundary_series) == num_steps
    assert len(u_in_series) == num_steps
    assert len(f_out_series) == num_steps
    assert len(residual_inflow_series) == num_steps
    assert len(residual_outflow_series) == num_steps

    for ramp in ramp_ids:
        assert len(observed_release_series[ramp]) == num_steps
        assert len(ramp_arrival_series[ramp]) == num_steps

    for step in range(num_steps):
        assert list(u_in_series[step].keys()) == cell_ids
        assert list(f_out_series[step].keys()) == cell_ids
        assert list(residual_inflow_series[step].keys()) == cell_ids
        assert list(residual_outflow_series[step].keys()) == cell_ids

        # Avila must not be embedded in ordinary u_in_series.
        expected_cell9_regular_inflow = float(
            undetected_entry_per_15sec_by_cell[merge_ramp_cell]
        )
        actual_cell9_regular_inflow = float(u_in_series[step][merge_ramp_cell])
        assert abs(actual_cell9_regular_inflow - expected_cell9_regular_inflow) < 1e-9

    x_current = mainline_initial_state.copy()
    R_current = ramp_queue_0.copy()
    B_current = external_queue_0.copy()
    upstream_boundary_queue_current = 0.0

    history = {
        "step": [],
        "x": [],
        "R": [],
        "B": [],
        "q_in": [],
        "q_out": [],
        "u_in": [],
        "f_out": [],
        "residual_inflow": [],
        "residual_outflow": [],
        "actual_f_out": [],
        "observed_release": [],
        "actual_release": [],
        "ramp_arrival": [],
        "spillback": [],
        "controllable_onramp_in": [],
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

    for step in range(num_steps):
        q_in_boundary_step = float(q_in_boundary_series[step])
        observed_release_step = {
            ramp: float(observed_release_series[ramp][step]) for ramp in ramp_ids
        }
        ramp_arrival_step = {
            ramp: float(ramp_arrival_series[ramp][step]) for ramp in ramp_ids
        }

        u_in_step = u_in_series[step]
        f_out_step = f_out_series[step]
        residual_inflow_step = residual_inflow_series[step]
        residual_outflow_step = residual_outflow_series[step]

        # Generic ramp update excludes Avila.
        generic_ramp_arrival_step = ramp_arrival_step.copy()
        generic_commanded_release_step = observed_release_step.copy()
        generic_ramp_arrival_step[merge_ramp_id] = 0.0
        generic_commanded_release_step[merge_ramp_id] = 0.0

        (
            R_next,
            B_next,
            spillback_by_ramp,
            actual_release_step,
        ) = ramp_next_queue_with_spillback(
            R_current=R_current,
            B_current=B_current,
            ramp_arrival_step=generic_ramp_arrival_step,
            commanded_release_step=generic_commanded_release_step,
            ramp_max_queue_by_u=ramp_max_queue_by_u,
        )

        # Avila request is capped by available demand and historical release command.
        avila_available_demand = (
            float(R_current[merge_ramp_id])
            + float(B_current[merge_ramp_id])
            + float(ramp_arrival_step[merge_ramp_id])
        )
        avila_commanded_release = float(observed_release_step[merge_ramp_id])
        avila_release_request = min(
            avila_available_demand,
            avila_commanded_release,
        )

        (
            x_next,
            q_out,
            q_in,
            sending,
            receiving,
            actual_f_out,
            avila_accepted,
            upstream_boundary_queue_next,
            upstream_boundary_delay,
        ) = ctm_15sec_step(
            x_current=x_current,
            q_in_boundary_step=q_in_boundary_step,
            u_in_step=u_in_step,
            f_out_step=f_out_step,
            avila_release_demand=avila_release_request,
            inflow_capacity=inflow_capacity,
            outflow_capacity=outflow_capacity,
            physical_capacity=physical_capacity,
            movement_factor_by_cell=movement_factor_by_cell,
            wave_speed_ratio_by_cell=wave_speed_ratio_by_cell,
            upstream_boundary_queue=upstream_boundary_queue_current,
            exit_split_by_cell=exit_split_by_cell,
            merge_priority=MERGE_PRIORITY,
        )

        # Update Avila queues after merge acceptance.
        avila_remaining = max(0.0, avila_available_demand - float(avila_accepted))
        avila_max_queue = float(ramp_max_queue_by_u[merge_ramp_id])
        R_next[merge_ramp_id] = min(avila_remaining, avila_max_queue)
        B_next[merge_ramp_id] = max(0.0, avila_remaining - avila_max_queue)
        spillback_by_ramp[merge_ramp_id] = B_next[merge_ramp_id]
        actual_release_step[merge_ramp_id] = float(avila_accepted)

        # Doorway/control penalty uses actual ramp releases, including accepted Avila.
        controllable_onramp_in_step = build_controllable_onramp_in_from_actual_release(
            actual_release_step
        )

        _, total_local_delay = ramp_delay_with_cap(
            R_current=R_current,
            R_next=R_next,
            B_current=B_current,
            B_next=B_next,
            ramp_arrival_step=ramp_arrival_step,
            commanded_release_step=observed_release_step,
            actual_release_step=actual_release_step,
            delta_t=delta_t,
        )

        _, _, L_fair = fairness_penalty_one_step(
            R_next=R_next,
            ramp_name_map=ramp_name_map,
            ramp_max_queue_named=ramp_max_queue_named,
            gamma=gamma,
        )

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
            delta_t=delta_t,
        )

        if use_clipped_mainline_delay:
            total_mainline_delay = total_mainline_delay_clipped + upstream_boundary_delay
        else:
            total_mainline_delay = total_mainline_delay_raw + upstream_boundary_delay

        capacity_info = capacity_penalty_one_step(
            q_in=q_in,
            u_in_step=u_in_step,
            controllable_onramp_in_step=controllable_onramp_in_step,
            x_next=x_next,
            inflow_capacity=inflow_capacity,
            safe_threshold_capacity=safe_threshold_capacity,
            physical_capacity=physical_capacity,
            spillback_by_ramp=spillback_by_ramp,
            lambda_1=lambda_1,
            lambda_2=lambda_2,
            lambda_3=lambda_3,
            lambda_4=lambda_4,
        )

        total_objective = (
            total_mainline_delay
            + total_local_delay
            + L_fair
            + capacity_info["total_capacity_penalty"]
        )

        history["step"].append(step)
        history["x"].append(x_next.copy())
        history["R"].append(R_next.copy())
        history["B"].append(B_next.copy())
        history["q_in"].append(q_in.copy())
        history["q_out"].append(q_out.copy())
        history["u_in"].append(u_in_step.copy())
        history["f_out"].append(f_out_step.copy())
        history["residual_inflow"].append(residual_inflow_step.copy())
        history["residual_outflow"].append(residual_outflow_step.copy())
        history["actual_f_out"].append(actual_f_out.copy())
        history["observed_release"].append(observed_release_step.copy())
        history["actual_release"].append(actual_release_step.copy())
        history["ramp_arrival"].append(ramp_arrival_step.copy())
        history["spillback"].append(spillback_by_ramp.copy())
        history["controllable_onramp_in"].append(controllable_onramp_in_step.copy())
        history["avila_available_demand"].append(float(avila_available_demand))
        history["avila_commanded_release"].append(float(avila_commanded_release))
        history["avila_release_request"].append(float(avila_release_request))
        history["avila_release_demand"].append(float(avila_release_request))
        history["avila_accepted"].append(float(avila_accepted))
        history["upstream_boundary_queue"].append(float(upstream_boundary_queue_next))
        history["upstream_boundary_delay"].append(float(upstream_boundary_delay))
        history["mainline_delay"].append(float(total_mainline_delay))
        history["mainline_delay_raw"].append(float(total_mainline_delay_raw))
        history["mainline_delay_clipped"].append(float(total_mainline_delay_clipped))
        history["local_delay"].append(float(total_local_delay))
        history["fairness_penalty"].append(float(L_fair))
        history["doorway_penalty"].append(float(capacity_info["total_doorway_penalty"]))
        history["safe_penalty"].append(float(capacity_info["total_safe_threshold_penalty"]))
        history["physical_penalty"].append(float(capacity_info["total_physical_capacity_penalty"]))
        history["spillback_penalty"].append(float(capacity_info["total_spillback_penalty"]))
        history["capacity_penalty"].append(float(capacity_info["total_capacity_penalty"]))
        history["total_objective"].append(float(total_objective))

        x_current = x_next.copy()
        R_current = R_next.copy()
        B_current = B_next.copy()
        upstream_boundary_queue_current = float(upstream_boundary_queue_next)

    history["x_final"] = x_current.copy()
    history["R_final"] = R_current.copy()
    history["B_final"] = B_current.copy()
    history["upstream_boundary_queue_final"] = upstream_boundary_queue_current

    return history


# Totals / service metrics
def compute_totals(history: dict[str, Any]) -> dict[str, float]:
    totals = {
        "mainline_delay": sum(history["mainline_delay"]),
        "mainline_delay_raw": sum(history["mainline_delay_raw"]),
        "mainline_delay_clipped": sum(history["mainline_delay_clipped"]),
        "upstream_boundary_delay": sum(history["upstream_boundary_delay"]),
        "local_delay": sum(history["local_delay"]),
        "fairness_penalty": sum(history["fairness_penalty"]),
        "doorway_penalty": sum(history["doorway_penalty"]),
        "safe_penalty": sum(history["safe_penalty"]),
        "physical_penalty": sum(history["physical_penalty"]),
        "spillback_penalty": sum(history["spillback_penalty"]),
    }

    totals["capacity_penalty"] = (
        totals["doorway_penalty"]
        + totals["safe_penalty"]
        + totals["physical_penalty"]
        + totals["spillback_penalty"]
    )

    totals["raw_objective"] = (
        totals["mainline_delay"]
        + totals["local_delay"]
        + totals["fairness_penalty"]
        + totals["capacity_penalty"]
    )

    return totals



def compute_service_metrics(history: dict[str, Any]) -> dict[str, float]:
    total_initial_R = sum(float(ramp_queue_0[ramp]) for ramp in ramp_ids)
    total_initial_B = sum(float(external_queue_0.get(ramp, 0.0)) for ramp in ramp_ids)
    total_arrivals = sum(
        float(ramp_arrival_series[ramp][step])
        for ramp in ramp_ids
        for step in range(num_steps)
    )
    total_actual_release = sum(
        float(history["actual_release"][step][ramp])
        for ramp in ramp_ids
        for step in range(num_steps)
    )
    total_final_R = sum(float(history["R_final"][ramp]) for ramp in ramp_ids)
    total_final_B = sum(float(history["B_final"][ramp]) for ramp in ramp_ids)

    total_demand_to_account = total_initial_R + total_initial_B + total_arrivals

    ramp_mass_residual = (
        total_initial_R
        + total_initial_B
        + total_arrivals
        - total_actual_release
        - total_final_R
        - total_final_B
    )

    served_fraction = (
        total_actual_release / total_demand_to_account
        if total_demand_to_account > 0
        else 1.0
    )

    return {
        "initial_physical_ramp_queue_R": total_initial_R,
        "initial_external_spillback_queue_B": total_initial_B,
        "total_ramp_arrivals": total_arrivals,
        "total_actual_release": total_actual_release,
        "final_physical_ramp_queue_R": total_final_R,
        "final_external_spillback_queue_B": total_final_B,
        "ramp_mass_residual": ramp_mass_residual,
        "total_ramp_demand_to_account": total_demand_to_account,
        "served_fraction": served_fraction,
        "final_upstream_boundary_queue": float(
            history["upstream_boundary_queue_final"]
        ),
    }



def print_comparison(name: str, reproduced: dict[str, float], official: dict[str, float]):
    print(f"\nCHECK AGAINST OFFICIAL {name}")
    max_abs_diff = 0.0

    for key, reproduced_value in reproduced.items():
        if key not in official:
            print(key, "| reproduced =", round(reproduced_value, 10), "| official = MISSING")
            continue

        official_value = float(official[key])
        difference = float(reproduced_value) - official_value
        max_abs_diff = max(max_abs_diff, abs(difference))

        print(
            key,
            "| reproduced =",
            round(float(reproduced_value), 10),
            "| official =",
            round(official_value, 10),
            "| diff =",
            round(difference, 12),
        )

    print("Max abs diff:", max_abs_diff)
    return max_abs_diff


# Main
if __name__ == "__main__":
    history = simulate_state_based_benchmark_480_steps()
    totals = compute_totals(history)
    service_metrics = compute_service_metrics(history)

    final_x = history["x_final"]
    final_R = history["R_final"]
    final_B = history["B_final"]
    final_spillback = history["spillback"][-1]

    print("OFFICIAL 9-CELL / 15-SEC CTM REPRODUCTION")
    print("num_steps:", num_steps)
    print("delta_t:", delta_t)
    print("arrival_multiplier:", arrival_multiplier)
    print("merge_ramp_id:", merge_ramp_id)
    print("merge_ramp_cell:", merge_ramp_cell)
    print("MERGE_PRIORITY:", MERGE_PRIORITY)

    print("\nFINAL MAINLINE STATE AFTER", num_steps, "STEPS")
    for cell in cell_ids:
        print(cell, ":", round(float(final_x[cell]), 6))

    print("\nFINAL PHYSICAL RAMP QUEUES AFTER", num_steps, "STEPS")
    for ramp in ramp_ids:
        print(ramp, ":", round(float(final_R[ramp]), 6))

    print("\nFINAL EXTERNAL SPILLBACK QUEUES AFTER", num_steps, "STEPS")
    for ramp in ramp_ids:
        print(ramp, ":", round(float(final_B[ramp]), 6))

    print("\nSPILLBACK IN FINAL STEP")
    for ramp in ramp_ids:
        print(ramp, ":", round(float(final_spillback[ramp]), 6))

    print("\nACCUMULATED BENCHMARK TOTALS")
    for key, value in totals.items():
        print(key, "=", round(float(value), 6))

    print("\nRAMP SERVICE / CONSERVATION METRICS")
    for key, value in service_metrics.items():
        print(key, "=", round(float(value), 8))

    if abs(service_metrics["ramp_mass_residual"]) < 1e-8:
        print("PASS: ramp demand is conserved.")
    else:
        print("FAIL: ramp demand is not conserved.")

    total_diff = print_comparison("BENCHMARK TOTALS", totals, official_totals)

    service_diff = 0.0
    if official_service_metrics:
        service_diff = print_comparison(
            "SERVICE METRICS",
            service_metrics,
            official_service_metrics,
        )

    print("\nMAXIMUM CELL OCCUPANCY")
    for cell in cell_ids:
        max_x = max(float(step_x[cell]) for step_x in history["x"])
        max_x = max(max_x, float(final_x[cell]))
        print(
            cell,
            "| max x =",
            round(max_x, 6),
            "| X_safe =",
            round(float(safe_threshold_capacity[cell]), 6),
            "| N_max =",
            round(float(physical_capacity[cell]), 6),
        )

    print("\nMAXIMUM PHYSICAL RAMP QUEUE")
    for ramp in ramp_ids:
        max_r = max(float(step_r[ramp]) for step_r in history["R"])
        max_r = max(max_r, float(final_R[ramp]))
        print(
            ramp,
            "| max R =",
            round(max_r, 6),
            "| R_max =",
            round(float(ramp_max_queue_by_u[ramp]), 6),
        )

    print("\nMAXIMUM EXTERNAL SPILLBACK QUEUE")
    for ramp in ramp_ids:
        max_b = max(float(step_b[ramp]) for step_b in history["B"])
        max_b = max(max_b, float(final_B[ramp]))
        print(ramp, "| max B =", round(max_b, 6))

    print("\nMAXIMUM SPILLBACK PENALTY STATE")
    for ramp in ramp_ids:
        max_s = max(float(step_s[ramp]) for step_s in history["spillback"])
        print(ramp, "| max spillback =", round(max_s, 6))

    if total_diff < 1e-8 and service_diff < 1e-8:
        print("\nPASS: Python reproduction matches official notebook export.")
    else:
        raise AssertionError(
            "Python reproduction does not match official notebook export. "
            f"total_diff={total_diff}, service_diff={service_diff}"
        )
