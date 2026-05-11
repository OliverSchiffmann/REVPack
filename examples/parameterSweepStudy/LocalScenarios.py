import importlib.util
import os
import sys
import asyncio
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed

# Import the simulation runner logic
from examples.simulation_runner import run_simulation

def worker_task(task_args):
    """Runs the simulation for a single scenario and seed in a separate process."""
    scenario_id, config, seed = task_args
    try:
        # Run the simulation core
        results, report = asyncio.run(run_simulation(config, seed))

        # Output results directly as a JSON payload
        output_data = {
            "metadata": {
                "Scenario": scenario_id,
                "Seed": seed
            },
            "report": report
        }
        return f"HPC_JSON_RESULT::{json.dumps(output_data)}\n"
    except Exception as e:
        return f"ERROR::Scenario_{scenario_id}::Seed_{seed}::{str(e)}\n"

if __name__ == "__main__":
    # --- Configuration ---
    SCENARIO_FILE = "examples/parameterSweepStudy/ofat_parameters_v2.py"
    OUTPUT_FILE = "examples/parameterSweepStudy/Outputs/local/ofat_results.txt"
    SEEDS = 1
    
    # Default to using all available cores except one (so your computer remains usable)
    WORKERS = max(1, multiprocessing.cpu_count() - 2)
    
    # 1. Load the scenario config
    if not os.path.exists(SCENARIO_FILE):
        print(f"Error: Scenario file '{SCENARIO_FILE}' not found.")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("scenario_module", SCENARIO_FILE)
    if spec is None or spec.loader is None:
        print(f"Error: Could not load scenario file '{SCENARIO_FILE}'.")
        sys.exit(1)
    scenario_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenario_module)
    
    SCENARIOS = scenario_module.SCENARIOS
    
    # 2. Prepare the tasks
    tasks = []
    for scenario_id, config in SCENARIOS.items():
        for seed in range(1, SEEDS + 1):
            tasks.append((scenario_id, config, seed))
            
    total_tasks = len(tasks)
    print(f"Prepared {total_tasks} tasks from {len(SCENARIOS)} scenarios, running with {SEEDS} seeds each.")
    print(f"Starting execution with {WORKERS} parallel workers...\n")

    os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_FILE)), exist_ok=True)

    # 3. Execute in parallel and write to output file
    completed = 0
    with open(OUTPUT_FILE, "w") as f:
        with ProcessPoolExecutor(max_workers=WORKERS) as executor:
            futures = {executor.submit(worker_task, task): task for task in tasks}
            
            for future in as_completed(futures):
                f.write(future.result())
                f.flush() # Ensure it writes to disk immediately
                completed += 1
                print(f"\rProgress: {completed}/{total_tasks} ({(completed/total_tasks)*100:.1f}%) complete.", end="")

    print(f"\n\nAll tasks complete. Results saved to {OUTPUT_FILE}")