"""Run the fully open benchmark and clearance using the current CTM and PeMS data."""

import argparse
import contextlib
import io
import json
import math
from pathlib import Path


_WINDOW_KEYS = {
    "mainline_tts": "mainline_tts",
    "ramp_queue_tts": "ramp_queue_tts",
    "upstream_boundary_tts": "upstream_boundary_tts",
    "external_entry_tts": "external_entry_tts",
    "fairness_penalty": "fairness_penalty",
    "safe_exposure": "safe_exposure",
    "spillback_exposure": "spillback_exposure",
    "weighted_safe_penalty": "weighted_safe_penalty",
    "weighted_spillback_penalty": "weighted_spillback_penalty",
    "raw_objective": "total_objective",
}


def load_benchmark(project_dir):
    """Build the corrected benchmark from PeMS in memory, through the export setup."""
    path = Path(project_dir).resolve() / "Benchmark_calculation.ipynb"
    if not path.is_file():
        raise FileNotFoundError(f"Benchmark notebook not found: {path}")
    notebook = json.loads(path.read_text(encoding="utf-8-sig"))
    sources = [
        (number, "".join(cell["source"]))
        for number, cell in enumerate(notebook["cells"], start=1)
        if cell["cell_type"] == "code"
    ]
    save_marker = "# 7. Save pickle file"
    if sum(save_marker in source for _, source in sources) != 1:
        raise ValueError(f"Cannot locate the corrected benchmark export in {path}")

    namespace = {"__file__": str(path), "display": lambda *_: None}
    with contextlib.redirect_stdout(io.StringIO()):
        for number, source in sources:
            end_of_setup = save_marker in source
            if end_of_setup:
                source = source.partition(save_marker)[0]
            # The benchmark's setup and simulation do not call plotting functions.
            ignored = {"%matplotlib inline", "import matplotlib.pyplot as plt", "import seaborn as sns"}
            source = "\n".join(line for line in source.splitlines() if line.strip() not in ignored)
            # Resolve PeMS paths from the supplied notebook without changing process cwd.
            source = source.replace("start = Path.cwd().resolve()", "start = Path(__file__).resolve().parent")
            exec(compile(source, f"{path} cell {number}", "exec"), namespace)
            if end_of_setup:
                break
    return namespace


def _inventory(mainline, ramp_queue, spillback, boundary_queue, external_queue):
    return math.fsum((
        math.fsum(mainline.values()),
        math.fsum(ramp_queue.values()),
        math.fsum(spillback.values()),
        boundary_queue,
        math.fsum(external_queue.values()),
    ))


def _clearance_tail(model, history, *, tolerance=1e-7, max_steps=480):
    """Clear all remaining vehicles through the same CTM with no new demand."""
    inputs = model["shared_benchmark_inputs"]
    cells = model["cell_ids"]
    ramps = inputs["ramp_ids"]
    step_ctm = model["ctm_15sec_step"]
    advance_ramp_queues = model["ramp_next_queue_after_actual_release"]
    fairness_penalty = model["fairness_penalty_one_step"]
    exposure_penalty = model["exposure_penalty_one_step"]
    minutes = inputs["delta_t"]
    ramp_storage = inputs["ramp_max_queue_by_u"]
    zero_cell_flow = dict.fromkeys(cells, 0.0)

    mainline = history["x_final"]
    ramp_queue = history["R_final"]
    spillback = history["B_final"]
    boundary_queue = history["upstream_boundary_queue_final"]
    external_queue = history["external_entry_queue_final"]
    initial = remaining = _inventory(mainline, ramp_queue, spillback, boundary_queue, external_queue)
    step_costs = {key: [] for key in _WINDOW_KEYS}
    discharged = []

    while remaining > tolerance and len(discharged) < max_steps:
        waiting = {ramp: ramp_queue[ramp] + spillback[ramp] for ramp in ramps}
        (
            next_mainline, mainline_out, _, _, _, _, exit_flow, _, _, accepted_release,
            _, next_boundary_queue, boundary_tts, _, _, next_external_queue,
        ) = step_ctm(
            x_current=mainline,
            q_in_boundary_step=0.0,
            external_inflow_step=zero_cell_flow,
            fixed_outflow_step=zero_cell_flow,
            requested_release_step=waiting,
            inflow_capacity=inputs["inflow_capacity"],
            outflow_capacity=inputs["outflow_capacity"],
            physical_capacity=inputs["physical_capacity"],
            movement_factor_by_cell=inputs["movement_factor_by_cell"],
            wave_speed_ratio_by_cell=inputs["wave_speed_ratio_by_cell"],
            upstream_boundary_queue=boundary_queue,
            exit_split_by_cell=inputs["exit_split_by_cell"],
            merge_priority=inputs["MERGE_PRIORITY"],
            external_entry_queue=external_queue,
        )
        next_ramp_queue, next_spillback, _ = advance_ramp_queues(
            available_demand_step=waiting,
            actual_release_step=accepted_release,
            ramp_max_queue_by_u=ramp_storage,
        )
        _, _, _, fairness = fairness_penalty(
            R_current=ramp_queue,
            B_current=spillback,
            R_next=next_ramp_queue,
            B_next=next_spillback,
            ramp_max_queue_by_u=ramp_storage,
            delta_t=minutes,
            gamma=inputs["gamma"],
        )
        exposures = exposure_penalty(
            x_current=mainline,
            x_next=next_mainline,
            B_current=spillback,
            B_next=next_spillback,
            safe_threshold_capacity=inputs["safe_threshold_capacity"],
            delta_t=minutes,
            lambda_safe=inputs["lambda_safe"],
            lambda_spillback=inputs["lambda_spillback"],
        )
        mainline_tts = 0.5 * minutes * (math.fsum(mainline.values()) + math.fsum(next_mainline.values()))
        ramp_tts = 0.5 * minutes * math.fsum(
            waiting[ramp] + next_ramp_queue[ramp] + next_spillback[ramp] for ramp in ramps
        )
        external_tts = 0.5 * minutes * (math.fsum(external_queue.values()) + math.fsum(next_external_queue.values()))
        objective = math.fsum((
            inputs["AW"] * mainline_tts, ramp_tts, boundary_tts, external_tts, fairness,
            exposures["weighted_safe_penalty"], exposures["weighted_spillback_penalty"],
        ))
        costs = {
            "mainline_tts": mainline_tts,
            "ramp_queue_tts": ramp_tts,
            "upstream_boundary_tts": boundary_tts,
            "external_entry_tts": external_tts,
            "fairness_penalty": fairness,
            "raw_objective": objective,
            **exposures,
        }
        for key, values in step_costs.items():
            values.append(costs[key])

        discharged.append(mainline_out[cells[-1]] + math.fsum(exit_flow.values()))
        mainline, ramp_queue, spillback = next_mainline, next_ramp_queue, next_spillback
        boundary_queue, external_queue = next_boundary_queue, next_external_queue
        remaining = _inventory(mainline, ramp_queue, spillback, boundary_queue, external_queue)

    if remaining > tolerance:
        raise RuntimeError(f"Clearance stopped after {max_steps} steps with {remaining:.6g} vehicles remaining")
    mass_error = initial - math.fsum(discharged) - remaining
    if abs(mass_error) > 1e-7:
        raise AssertionError(f"Clearance vehicle balance error: {mass_error:.6g}")
    return (
        {key: math.fsum(values) for key, values in step_costs.items()},
        {"terminal_steps": len(discharged), "terminal_remaining_vehicles": remaining, "terminal_mass_residual": mass_error},
    )


def score_policy(model, history):
    """Return adjusted, window-only, and clearance-only costs in vehicle-minutes.

    Unprefixed costs include clearance. Window and clearance costs use the
    prefixes ``window_`` and ``terminal_``. Service and inventory fields refer
    to the end of the two-hour window, before clearance begins.
    """
    inputs = model["shared_benchmark_inputs"]
    window = {key: math.fsum(history[name]) for key, name in _WINDOW_KEYS.items()}
    terminal, diagnostics = _clearance_tail(model, history)
    totals = {key: window[key] + terminal[key] for key in window}
    totals.update({f"window_{key}": value for key, value in window.items()})
    totals.update({f"terminal_{key}": value for key, value in terminal.items()})

    arrivals = math.fsum(value for series in inputs["ramp_arrival_series"].values() for value in series)
    initial_ramp = math.fsum(inputs["ramp_queue_0"].values()) + math.fsum(inputs["ramp_overflow_queue_0"].values())
    requested_service = initial_ramp + arrivals
    actual = math.fsum(value for step in history["actual_release"] for value in step.values())
    totals.update({
        "served_fraction": actual / requested_service if requested_service > 0.0 else 1.0,
        "total_ramp_arrivals": arrivals,
        "total_actual_release": actual,
        "final_ramp_queue": math.fsum(history["R_final"].values()) + math.fsum(history["B_final"].values()),
        "final_mainline_inventory": math.fsum(history["x_final"].values()),
        "final_upstream_boundary_queue": history["upstream_boundary_queue_final"],
        "final_external_entry_queue": math.fsum(history["external_entry_queue_final"].values()),
        "final_total_inventory": _inventory(
            history["x_final"], history["R_final"], history["B_final"],
            history["upstream_boundary_queue_final"], history["external_entry_queue_final"],
        ),
        **diagnostics,
    })
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Folder containing Benchmark_calculation.ipynb and the two PeMS input files.",
    )
    args = parser.parse_args()
    model = load_benchmark(args.project_dir)
    inputs = model["shared_benchmark_inputs"]
    score = score_policy(model, model["official_benchmark_history"])

    expected = inputs["official_totals"]
    for name in _WINDOW_KEYS:
        if not math.isclose(score[f"window_{name}"], expected[name], rel_tol=0.0, abs_tol=1e-7):
            raise RuntimeError(f"The calculated two-hour {name} differs from the benchmark notebook.")

    initial_ramp_inventory = math.fsum(inputs["ramp_queue_0"].values()) + math.fsum(
        inputs["ramp_overflow_queue_0"].values()
    )
    ramp_mass_residual = math.fsum((
        initial_ramp_inventory, score["total_ramp_arrivals"],
        -score["total_actual_release"], -score["final_ramp_queue"],
    ))
    if abs(ramp_mass_residual) > 1e-7:
        raise RuntimeError(f"Ramp vehicle balance failed: {ramp_mass_residual:.3g} vehicles.")

    terms = (
        ("Mainline travel time", "mainline_tts"),
        ("Ramp waiting time", "ramp_queue_tts"),
        ("Upstream waiting time", "upstream_boundary_tts"),
        ("External entry waiting time", "external_entry_tts"),
        ("Fairness penalty", "fairness_penalty"),
        ("Weighted safety penalty", "weighted_safe_penalty"),
        ("Weighted spillback penalty", "weighted_spillback_penalty"),
        ("Total cost", "raw_objective"),
    )
    print(f"Benchmark policy: {inputs['benchmark_policy_name']}")
    print(f"Scenario: {inputs['benchmark_date']} {inputs['benchmark_window_label']}")
    print(f"Steps: {inputs['num_steps']} at {inputs['delta_t'] * 60:g} seconds")
    print(f"Arrival multiplier: {inputs['arrival_multiplier']:g}")
    print(f"Avila merge priority: {inputs['MERGE_PRIORITY']:g}")
    print()
    print(f"{'Metric (vehicle-minutes)':<29} {'Two-hour':>13} {'Clearance':>13} {'Combined':>13}")
    for label, name in terms:
        print(f"{label:<29} {score[f'window_{name}']:13,.2f} "
              f"{score[f'terminal_{name}']:13,.2f} {score[name]:13,.2f}")
    print()
    print(f"Ramp demand served in two hours: {score['served_fraction']:.2%}")
    print(f"Vehicles left on ramps after two hours: {score['final_ramp_queue']:.3f}")
    print(f"Clearance steps: {score['terminal_steps']}")
    print(f"Ramp mass residual at two hours: {ramp_mass_residual:.3g} vehicles")
    print(f"Clearance mass residual: {score['terminal_mass_residual']:.3g} vehicles")
    print("PASS: exact CTM checks, two-hour objective totals, and vehicle balance.")


if __name__ == "__main__":
    main()
