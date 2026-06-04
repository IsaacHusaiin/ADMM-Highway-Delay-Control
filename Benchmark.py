# Official benchmark CTM reproduction
# Python .py version

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


# Source-of-truth variables

official_totals = get_input("official_totals")
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

ramp_ids = [
    f"u{i}"
    for i in range(1, 6)
]

mainline_initial_state = get_input("mainline_initial_state")
ramp_queue_0 = get_input("ramp_queue_0")

q_in_boundary_series = get_input("q_in_boundary_series")
observed_release_series = get_input("observed_release_series")
ramp_arrival_series = get_input("ramp_arrival_series")
f_out_series = get_input("f_out_series")

doorway_capacity = get_input("doorway_capacity")
safe_threshold_capacity = get_input("safe_threshold_capacity")
physical_capacity = get_input("physical_capacity")

ramp_name_map = get_input("ramp_name_map")
ramp_max_queue_named = get_input("ramp_max_queue_named")
tt_ff_min = get_input("tt_ff_min")


# Helper: convert ramp releases to CTM cell inflows
def build_uin(u_dict):
    return {
        "Cell 1": 0.0,
        "Cell 2": float(u_dict["u1"]),
        "Cell 3": 0.0,
        "Cell 4": float(u_dict["u2"]),
        "Cell 5": float(u_dict["u3"]),
        "Cell 6": float(u_dict["u4"]),
        "Cell 7": float(u_dict["u5"]),
        "Cell 8": 0.0,
    }


# Ramp queue update with spillback
def update_ramp_queues(
    ramp_queue_now,
    ramp_arrival,
    ramp_release,
    ramp_name_map,
    ramp_max_queue_named,
):
    ramp_next = {}
    spillback_by_ramp = {}

    for ramp in ramp_queue_now:
        R_now = float(ramp_queue_now[ramp])
        a_now = float(ramp_arrival[ramp])
        u_now = float(ramp_release[ramp])

        ramp_name = ramp_name_map[ramp]
        R_max = float(ramp_max_queue_named[ramp_name])

        R_raw = R_now + a_now - u_now

        R_next = min(R_raw, R_max)
        spillback = max(0.0, R_raw - R_max)

        ramp_next[ramp] = R_next
        spillback_by_ramp[ramp] = spillback

    return ramp_next, spillback_by_ramp


# Local ramp delay

def local_delay_one_step(ramp_queue_now, ramp_queue_next, delta_t):
    total_local_delay = 0.0
    for ramp in ramp_queue_now:
        R_now = float(ramp_queue_now[ramp])
        R_next = float(ramp_queue_next[ramp])

        D_local = ((R_now + R_next) / 2.0) * delta_t
        total_local_delay += D_local

    return total_local_delay


# Fairness penalty
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

        raw_stress = ramp_queue_next[ramp] / R_max
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
            float(doorway_capacity[cell])
        )

    # Receiving capacity for downstream cells
    for i in range(1, len(cells)):
        cell = cells[i]

        receiving[cell] = max(
            0.0,
            min(
                float(doorway_capacity[cell]),
                float(physical_capacity[cell]) - float(current_mainline_state[cell])
            )
        )

    # Mainline cell-to-cell flow
    for i in range(len(cells) - 1):
        current_cell = cells[i]
        next_cell = cells[i + 1]

        q_out[current_cell] = min(
            sending[current_cell],
            receiving[next_cell]
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
            max(0.0, available_before_offramp)
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

        # Clamp small negative delay.
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
            float(q_in[cell]) + float(u_in[cell]) - float(doorway_capacity[cell])
        )

        doorway_penalty += lambda_1 * doorway_overflow ** 2

    for cell in x_next:
        safe_overflow = max(
            0.0,
            float(x_next[cell]) - float(safe_threshold_capacity[cell])
        )

        physical_overflow = max(
            0.0,
            float(x_next[cell]) - float(physical_capacity[cell])
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

    history = {
        "step": [],
        "x": [],
        "R": [],
        "u_apply": [],
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

        u_in_t = build_uin(observed_release_t)

        ramp_queue_next, spillback_t = update_ramp_queues(
            ramp_queue_now=ramp_queue_current,
            ramp_arrival=ramp_arrival_t,
            ramp_release=observed_release_t,
            ramp_name_map=ramp_name_map,
            ramp_max_queue_named=ramp_max_queue_named,
        )

        local_delay_t = local_delay_one_step(
            ramp_queue_now=ramp_queue_current,
            ramp_queue_next=ramp_queue_next,
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
        history["x"].append(x_current.copy())
        history["R"].append(ramp_queue_current.copy())
        history["u_apply"].append(observed_release_t.copy())
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

    history["x_final"] = x_current.copy()
    history["R_final"] = ramp_queue_current.copy()

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


# Main execution

if __name__ == "__main__":

    history = simulate_observed_release_benchmark()
    totals = compute_totals(history)

    final_x = history["x_final"]
    final_R = history["R_final"]
    final_spillback = history["spillback"][-1]

    print("FINAL MAINLINE STATE AFTER", num_steps, "STEPS ")
    for cell in cell_order:
        print(cell, ":", round(final_x[cell], 3))

    print("\n FINAL RAMP QUEUES AFTER", num_steps, "STEPS ")
    for ramp in ramp_ids:
        print(ramp, ":", round(final_R[ramp], 3))

    print("\n SPILLBACK IN FINAL STEP ")
    for ramp in ramp_ids:
        print(ramp, ":", round(final_spillback[ramp], 3))

    print("\nACCUMULATED BASELINE TOTALS ")
    for key, value in totals.items():
        print(key, "=", round(value, 3))

    print("\n CHECK AGAINST OFFICIAL BENCHMARK TOTALS ")
    for key in totals:
        official_value = official_totals[key]
        reproduced_value = totals[key]
        difference = reproduced_value - official_value

        print(
            key,
            "| reproduced =",
            round(reproduced_value, 3),
            "| official =",
            round(official_value, 3),
            "| diff =",
            round(difference, 6),
        )

    print("\nMAXIMUM CELL OCCUPANCY ")
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

    print("\n MAXIMUM RAMP QUEUE ")
    for ramp in ramp_ids:
        max_r = max(step_r[ramp] for step_r in history["R"])
        max_r = max(max_r, final_R[ramp])

        print(ramp, "| max queue =", round(max_r, 3))

    print("\n MAXIMUM SPILLBACK ")
    for ramp in ramp_ids:
        max_s = max(step_s[ramp] for step_s in history["spillback"])

        print(ramp, "| max spillback =", round(max_s, 3))