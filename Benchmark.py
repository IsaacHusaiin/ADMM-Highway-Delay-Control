# Official benchmark CTM reproduction
# Python .py version
# Corrected version with persistent external spillback queue conservation.

from pathlib import Path
import pickle


# Load shared benchmark inputs

shared_inputs_path = Path("shared_benchmark_inputs.pkl")

if not shared_inputs_path.exists():
    raise FileNotFoundError(
        "shared_benchmark_inputs.pkl was not found. "
        "Run Benchmark_calculation.ipynb first and make sure the export cell completed."
    )

with open(shared_inputs_path, "rb") as file:
    shared = pickle.load(file)


def get_input(name):
    if name not in shared:
        raise KeyError(f"{name} was not found in shared_benchmark_inputs.pkl")
    return shared[name]


def get_optional_input(name, default_value):
    if name in shared:
        return shared[name]
    return default_value


# Source-of-truth variables

official_totals = get_input("official_totals")
official_service_metrics = get_optional_input("official_service_metrics", {})

num_steps = get_input("num_steps")
delta_t = get_input("delta_t")
gamma = get_input("gamma")
lambda_1 = get_input("lambda_1")
lambda_2 = get_input("lambda_2")
lambda_3 = get_input("lambda_3")
lambda_4 = get_input("lambda_4")

cell_order = [
    f"Cell {i}"
    for i in range(1, 9)
]

ramp_ids = get_optional_input(
    "ramp_ids",
    [
        f"u{i}"
        for i in range(1, 6)
    ],
)

mainline_initial_state = get_input("mainline_initial_state")
ramp_queue_0 = get_input("ramp_queue_0")
external_queue_0 = get_optional_input(
    "external_queue_0",
    {
        ramp: 0.0
        for ramp in ramp_ids
    },
)

q_in_boundary_series = get_input("q_in_boundary_series")
observed_release_series = get_input("observed_release_series")
ramp_arrival_series = get_input("ramp_arrival_series")
f_out_series = get_input("f_out_series")

doorway_capacity = get_input("doorway_capacity")
safe_threshold_capacity = get_input("safe_threshold_capacity")
physical_capacity = get_input("physical_capacity")

ramp_name_map = get_input("ramp_name_map")
ramp_max_queue_named = get_input("ramp_max_queue_named")
ramp_max_queue_by_u = get_optional_input("ramp_max_queue_by_u", None)
tt_ff_min = get_input("tt_ff_min")

if ramp_max_queue_by_u is None:
    ramp_max_queue_by_u = {}
    for ramp in ramp_ids:
        ramp_name = ramp_name_map[ramp]
        ramp_max_queue_by_u[ramp] = ramp_max_queue_named[ramp_name]


# Helper: convert actual ramp releases to CTM cell inflows

def build_uin(ramp_release_dict):
    return {
        "Cell 1": 0.0,
        "Cell 2": float(ramp_release_dict["u1"]),
        "Cell 3": 0.0,
        "Cell 4": float(ramp_release_dict["u2"]),
        "Cell 5": float(ramp_release_dict["u3"]),
        "Cell 6": float(ramp_release_dict["u4"]),
        "Cell 7": float(ramp_release_dict["u5"]),
        "Cell 8": 0.0,
    }


# Conservative ramp queue update with persistent external spillback/backlog

def update_ramp_queues(
    ramp_queue_now,
    external_queue_now,
    ramp_arrival,
    ramp_release_command,
    ramp_max_queue_by_u,
):
    ramp_next = {}
    external_next = {}
    spillback_by_ramp = {}
    actual_release = {}

    for ramp in ramp_queue_now:
        R_now = float(ramp_queue_now[ramp])
        B_now = float(external_queue_now.get(ramp, 0.0))
        a_now = float(ramp_arrival[ramp])
        u_command = float(ramp_release_command[ramp])
        R_max = float(ramp_max_queue_by_u[ramp])

        available = max(0.0, R_now) + max(0.0, B_now) + max(0.0, a_now)

        u_actual = min(
            max(0.0, u_command),
            available,
        )

        waiting_after_release = max(
            0.0,
            available - u_actual,
        )

        R_next = min(
            waiting_after_release,
            R_max,
        )

        B_next = max(
            0.0,
            waiting_after_release - R_max,
        )

        ramp_next[ramp] = R_next
        external_next[ramp] = B_next
        spillback_by_ramp[ramp] = B_next
        actual_release[ramp] = u_actual

    return ramp_next, external_next, spillback_by_ramp, actual_release


# Local ramp delay from physical queue plus persistent external queue

def local_delay_one_step(
    ramp_queue_now,
    ramp_queue_next,
    external_queue_now,
    external_queue_next,
    delta_t,
):
    total_local_delay = 0.0

    for ramp in ramp_queue_now:
        waiting_now = (
            float(ramp_queue_now[ramp])
            + float(external_queue_now.get(ramp, 0.0))
        )

        waiting_next = (
            float(ramp_queue_next[ramp])
            + float(external_queue_next.get(ramp, 0.0))
        )

        D_local = ((waiting_now + waiting_next) / 2.0) * delta_t
        total_local_delay += D_local

    return total_local_delay


# Fairness penalty based on physical ramp storage stress

def fairness_penalty_one_step(
    ramp_queue_next,
    ramp_name_map,
    ramp_max_queue_named,
    gamma,
):
    stress_capped = {}

    for ramp in ramp_queue_next:
        ramp_name = ramp_name_map[ramp]
        R_max = float(ramp_max_queue_named[ramp_name])

        raw_stress = float(ramp_queue_next[ramp]) / R_max
        stress_capped[ramp] = min(raw_stress, 1.0)

    ramps = list(stress_capped.keys())
    fairness_raw = 0.0

    for i in range(len(ramps)):
        for j in range(i + 1, len(ramps)):
            fairness_raw += (
                stress_capped[ramps[i]]
                - stress_capped[ramps[j]]
            ) ** 2

    fairness_penalty = gamma * fairness_raw

    return fairness_penalty


# CTM one-step update

def ctm_30sec_step(
    current_mainline_state,
    q_in_boundary,
    u_in,
    f_out_requested,
    doorway_capacity,
    physical_capacity,
):
    sending = {}
    receiving = {}
    q_out = {}
    q_in = {}
    x_next = {}
    actual_f_out = {}

    cells = list(current_mainline_state.keys())

    # Sending flow from each cell
    for cell in cells:
        sending[cell] = min(
            float(current_mainline_state[cell]),
            float(doorway_capacity[cell]),
        )

    # Receiving capacity for downstream cells
    for i in range(1, len(cells)):
        cell = cells[i]

        receiving[cell] = max(
            0.0,
            min(
                float(doorway_capacity[cell]),
                float(physical_capacity[cell]) - float(current_mainline_state[cell]),
            ),
        )

    # Mainline cell-to-cell flow
    for i in range(len(cells) - 1):
        current_cell = cells[i]
        next_cell = cells[i + 1]

        q_out[current_cell] = min(
            sending[current_cell],
            receiving[next_cell],
        )

    # Downstream discharge from final cell
    q_out[cells[-1]] = sending[cells[-1]]

    # Mainline inflow
    q_in[cells[0]] = float(q_in_boundary)

    for i in range(1, len(cells)):
        q_in[cells[i]] = q_out[cells[i - 1]]

    # Actual off-ramp flow is clipped so it cannot remove more vehicles
    # than are available after inflow and ramp inflow.
    for cell in cells:
        available_before_offramp = (
            float(current_mainline_state[cell])
            + float(q_in[cell])
            + float(u_in[cell])
            - float(q_out[cell])
        )

        requested_offramp = float(f_out_requested[cell])

        actual_f_out[cell] = min(
            requested_offramp,
            max(0.0, available_before_offramp),
        )

        x_next[cell] = (
            float(current_mainline_state[cell])
            + float(q_in[cell])
            + float(u_in[cell])
            - actual_f_out[cell]
            - float(q_out[cell])
        )

    return x_next, q_out, q_in, sending, receiving, actual_f_out


# Mainline delay

def mainline_delay_one_step(
    x_now,
    x_next,
    q_out,
    actual_f_out,
    tt_ff_min,
    delta_t,
):
    total_mainline_delay = 0.0

    for cell in x_now:
        TTT = ((float(x_now[cell]) + float(x_next[cell])) / 2.0) * delta_t

        free_flow_term = (
            float(q_out[cell])
            + float(actual_f_out[cell])
        ) * float(tt_ff_min[cell])

        D_main = TTT - free_flow_term
        D_main = max(0.0, D_main)

        total_mainline_delay += D_main

    return total_mainline_delay


# Capacity penalty

def capacity_penalty_one_step(
    q_in,
    u_in,
    x_next,
    doorway_capacity,
    safe_threshold_capacity,
    physical_capacity,
    spillback_by_ramp,
    lambda_1,
    lambda_2,
    lambda_3,
    lambda_4,
):
    doorway_penalty = 0.0
    safe_penalty = 0.0
    physical_penalty = 0.0
    spillback_penalty = 0.0

    for cell in q_in:
        doorway_overflow = max(
            0.0,
            float(q_in[cell]) + float(u_in[cell]) - float(doorway_capacity[cell]),
        )

        doorway_penalty += lambda_1 * doorway_overflow ** 2

    for cell in x_next:
        safe_overflow = max(
            0.0,
            float(x_next[cell]) - float(safe_threshold_capacity[cell]),
        )

        physical_overflow = max(
            0.0,
            float(x_next[cell]) - float(physical_capacity[cell]),
        )

        safe_penalty += lambda_2 * safe_overflow ** 2
        physical_penalty += lambda_3 * physical_overflow ** 2

    for ramp in spillback_by_ramp:
        spillback_penalty += lambda_4 * float(spillback_by_ramp[ramp]) ** 2

    capacity_penalty = (
        doorway_penalty
        + safe_penalty
        + physical_penalty
        + spillback_penalty
    )

    return {
        "doorway_penalty": doorway_penalty,
        "safe_penalty": safe_penalty,
        "physical_penalty": physical_penalty,
        "spillback_penalty": spillback_penalty,
        "capacity_penalty": capacity_penalty,
    }


# Simulate observed-release benchmark

def simulate_observed_release_benchmark():
    x_current = mainline_initial_state.copy()
    ramp_queue_current = ramp_queue_0.copy()
    external_queue_current = external_queue_0.copy()

    history = {
        "step": [],
        "x": [],
        "R": [],
        "B": [],
        "u_command": [],
        "u_apply": [],
        "actual_release": [],
        "ramp_arrival": [],
        "q_in": [],
        "q_out": [],
        "actual_f_out": [],
        "spillback": [],
        "mainline_delay": [],
        "local_delay": [],
        "fairness_penalty": [],
        "doorway_penalty": [],
        "safe_penalty": [],
        "physical_penalty": [],
        "spillback_penalty": [],
        "capacity_penalty": [],
        "total_objective": [],
    }

    for t in range(num_steps):
        observed_release_t = {
            ramp: float(observed_release_series[ramp][t])
            for ramp in ramp_ids
        }

        ramp_arrival_t = {
            ramp: float(ramp_arrival_series[ramp][t])
            for ramp in ramp_ids
        }

        q_in_boundary_t = float(q_in_boundary_series[t])
        f_out_requested_t = f_out_series[t]

        (
            ramp_queue_next,
            external_queue_next,
            spillback_t,
            actual_release_t,
        ) = update_ramp_queues(
            ramp_queue_now=ramp_queue_current,
            external_queue_now=external_queue_current,
            ramp_arrival=ramp_arrival_t,
            ramp_release_command=observed_release_t,
            ramp_max_queue_by_u=ramp_max_queue_by_u,
        )

        # Freeway ramp inflow must use actual released vehicles, not command.
        u_in_t = build_uin(actual_release_t)

        local_delay_t = local_delay_one_step(
            ramp_queue_now=ramp_queue_current,
            ramp_queue_next=ramp_queue_next,
            external_queue_now=external_queue_current,
            external_queue_next=external_queue_next,
            delta_t=delta_t,
        )

        fairness_penalty_t = fairness_penalty_one_step(
            ramp_queue_next=ramp_queue_next,
            ramp_name_map=ramp_name_map,
            ramp_max_queue_named=ramp_max_queue_named,
            gamma=gamma,
        )

        (
            x_next,
            q_out,
            q_in,
            sending,
            receiving,
            actual_f_out_t,
        ) = ctm_30sec_step(
            current_mainline_state=x_current,
            q_in_boundary=q_in_boundary_t,
            u_in=u_in_t,
            f_out_requested=f_out_requested_t,
            doorway_capacity=doorway_capacity,
            physical_capacity=physical_capacity,
        )

        mainline_delay_t = mainline_delay_one_step(
            x_now=x_current,
            x_next=x_next,
            q_out=q_out,
            actual_f_out=actual_f_out_t,
            tt_ff_min=tt_ff_min,
            delta_t=delta_t,
        )

        capacity_info_t = capacity_penalty_one_step(
            q_in=q_in,
            u_in=u_in_t,
            x_next=x_next,
            doorway_capacity=doorway_capacity,
            safe_threshold_capacity=safe_threshold_capacity,
            physical_capacity=physical_capacity,
            spillback_by_ramp=spillback_t,
            lambda_1=lambda_1,
            lambda_2=lambda_2,
            lambda_3=lambda_3,
            lambda_4=lambda_4,
        )

        total_objective_t = (
            mainline_delay_t
            + local_delay_t
            + fairness_penalty_t
            + capacity_info_t["capacity_penalty"]
        )

        history["step"].append(t + 1)
        history["x"].append(x_next.copy())
        history["R"].append(ramp_queue_next.copy())
        history["B"].append(external_queue_next.copy())
        history["u_command"].append(observed_release_t.copy())
        history["u_apply"].append(actual_release_t.copy())
        history["actual_release"].append(actual_release_t.copy())
        history["ramp_arrival"].append(ramp_arrival_t.copy())
        history["q_in"].append(q_in.copy())
        history["q_out"].append(q_out.copy())
        history["actual_f_out"].append(actual_f_out_t.copy())
        history["spillback"].append(spillback_t.copy())
        history["mainline_delay"].append(mainline_delay_t)
        history["local_delay"].append(local_delay_t)
        history["fairness_penalty"].append(fairness_penalty_t)
        history["doorway_penalty"].append(capacity_info_t["doorway_penalty"])
        history["safe_penalty"].append(capacity_info_t["safe_penalty"])
        history["physical_penalty"].append(capacity_info_t["physical_penalty"])
        history["spillback_penalty"].append(capacity_info_t["spillback_penalty"])
        history["capacity_penalty"].append(capacity_info_t["capacity_penalty"])
        history["total_objective"].append(total_objective_t)

        x_current = x_next.copy()
        ramp_queue_current = ramp_queue_next.copy()
        external_queue_current = external_queue_next.copy()

    history["x_final"] = x_current.copy()
    history["R_final"] = ramp_queue_current.copy()
    history["B_final"] = external_queue_current.copy()

    return history


# Totals helper

def compute_totals(history):
    totals = {
        "mainline_delay": sum(history["mainline_delay"]),
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


# Service and conservation helpers

def compute_service_metrics(history):
    total_initial_R = sum(
        float(ramp_queue_0[ramp])
        for ramp in ramp_ids
    )

    total_initial_B = sum(
        float(external_queue_0.get(ramp, 0.0))
        for ramp in ramp_ids
    )

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

    total_final_R = sum(
        float(history["R_final"][ramp])
        for ramp in ramp_ids
    )

    total_final_B = sum(
        float(history["B_final"][ramp])
        for ramp in ramp_ids
    )

    total_demand_to_account = (
        total_initial_R
        + total_initial_B
        + total_arrivals
    )

    ramp_mass_residual = (
        total_initial_R
        + total_initial_B
        + total_arrivals
        - total_actual_release
        - total_final_R
        - total_final_B
    )

    if total_demand_to_account > 0:
        served_fraction = total_actual_release / total_demand_to_account
    else:
        served_fraction = 1.0

    return {
        "initial_physical_ramp_queue_R": total_initial_R,
        "initial_external_spillback_queue_B": total_initial_B,
        "total_ramp_arrivals": total_arrivals,
        "total_ramp_demand_to_account": total_demand_to_account,
        "total_actual_release": total_actual_release,
        "final_physical_ramp_queue_R": total_final_R,
        "final_external_spillback_queue_B": total_final_B,
        "ramp_mass_residual": ramp_mass_residual,
        "served_fraction": served_fraction,
    }


# Main execution

if __name__ == "__main__":
    history = simulate_observed_release_benchmark()
    totals = compute_totals(history)
    service_metrics = compute_service_metrics(history)

    final_x = history["x_final"]
    final_R = history["R_final"]
    final_B = history["B_final"]
    final_spillback = history["spillback"][-1]

    print("FINAL MAINLINE STATE AFTER", num_steps, "STEPS")
    for cell in cell_order:
        print(cell, ":", round(final_x[cell], 3))

    print("\nFINAL RAMP QUEUES AFTER", num_steps, "STEPS")
    for ramp in ramp_ids:
        print(ramp, ":", round(final_R[ramp], 3))

    print("\nFINAL EXTERNAL SPILLBACK QUEUES AFTER", num_steps, "STEPS")
    for ramp in ramp_ids:
        print(ramp, ":", round(final_B[ramp], 3))

    print("\nSPILLBACK IN FINAL STEP")
    for ramp in ramp_ids:
        print(ramp, ":", round(final_spillback[ramp], 3))

    print("\nACCUMULATED BASELINE TOTALS")
    for key, value in totals.items():
        print(key, "=", round(value, 6))

    print("\nRAMP SERVICE / CONSERVATION METRICS")
    for key, value in service_metrics.items():
        print(key, "=", round(value, 8))

    if abs(service_metrics["ramp_mass_residual"]) < 1e-8:
        print("PASS: ramp demand is conserved.")
    else:
        print("FAIL: ramp demand is not conserved.")

    print("\nCHECK AGAINST OFFICIAL BENCHMARK TOTALS")
    for key in totals:
        official_value = official_totals[key]
        reproduced_value = totals[key]
        difference = reproduced_value - official_value

        print(
            key,
            "| reproduced =",
            round(reproduced_value, 6),
            "| official =",
            round(official_value, 6),
            "| diff =",
            round(difference, 9),
        )

    if official_service_metrics:
        print("\nCHECK AGAINST OFFICIAL SERVICE METRICS")
        for key in service_metrics:
            if key in official_service_metrics:
                official_value = official_service_metrics[key]
                reproduced_value = service_metrics[key]
                difference = reproduced_value - official_value

                print(
                    key,
                    "| reproduced =",
                    round(reproduced_value, 8),
                    "| official =",
                    round(official_value, 8),
                    "| diff =",
                    round(difference, 10),
                )

    print("\nMAXIMUM CELL OCCUPANCY")
    for cell in cell_order:
        max_x = max(step_x[cell] for step_x in history["x"])
        max_x = max(max_x, final_x[cell])

        print(
            cell,
            "| max x =",
            round(max_x, 3),
            "| X_safe =",
            round(safe_threshold_capacity[cell], 3),
            "| N_max =",
            round(physical_capacity[cell], 3),
        )

    print("\nMAXIMUM PHYSICAL RAMP QUEUE")
    for ramp in ramp_ids:
        max_r = max(step_r[ramp] for step_r in history["R"])
        max_r = max(max_r, final_R[ramp])

        print(
            ramp,
            "| max R =",
            round(max_r, 3),
            "| R_max =",
            round(float(ramp_max_queue_by_u[ramp]), 3),
        )

    print("\nMAXIMUM EXTERNAL SPILLBACK QUEUE")
    for ramp in ramp_ids:
        max_b = max(step_b[ramp] for step_b in history["B"])
        max_b = max(max_b, final_B[ramp])

        print(ramp, "| max B =", round(max_b, 3))

    print("\nMAXIMUM SPILLBACK PENALTY STATE")
    for ramp in ramp_ids:
        max_s = max(step_s[ramp] for step_s in history["spillback"])

        print(ramp, "| max spillback =", round(max_s, 3))
