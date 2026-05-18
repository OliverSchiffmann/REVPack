import argparse
import importlib.util
import os
import sys
import multiprocessing
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_hpc_main(scenario_file, chunk_ids, seed):
    """Calls HPC_main.py as a subprocess, mimicking a SLURM array job."""
    cmd = (
        [
            sys.executable,  # Uses the current active python environment
            "examples/parameterSweepStudy/HPC_main.py",
            "--scenario_file",
            scenario_file,
            "--scenarios",
        ]
        + [str(c) for c in chunk_ids]
        + ["--seed", str(seed)]
    )

    try:
        # capture_output catches prints (like our JSON) natively
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"ERROR::Subprocess failed with exit code {e.returncode}\n{e.stderr}\n"


if __name__ == "__main__":
    # Add the usual selection of parameters so that you can run it from the command line if you wish, I prefer running in the IDE so will change the default values to suit my needs.
    parser = argparse.ArgumentParser(
        description="Local runner that simulates SLURM by calling HPC_main.py"
    )
    parser.add_argument(
        "--scenario_file",
        type=str,
        default="examples/parameterSweepStudy/ofat_parameters_v2.py",
        help="Scenario dictionary file",
    )
    parser.add_argument(
        "--output_file",
        type=str,
        default="examples/parameterSweepStudy/Outputs/local/ofat_results.txt",
        help="Output file path",
    )
    parser.add_argument(
        "--chunk_size",
        type=int,
        default=10,
        help="Number of scenarios to run per HPC_main.py process",
    )
    parser.add_argument(
        "--seeds", type=int, default=1, help="Number of random seeds per scenario"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, multiprocessing.cpu_count() - 2),
        help="Number of parallel workers",
    )
    args = parser.parse_args()

    # 1. Load the scenario config just to extract the available scenario keys (IDs)
    if not os.path.exists(args.scenario_file):
        print(f"Error: Scenario file '{args.scenario_file}' not found.")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("scenario_module", args.scenario_file)
    if spec is None or spec.loader is None:
        print(f"Error: Could not load scenario file '{args.scenario_file}'.")
        sys.exit(1)
    scenario_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenario_module)

    SCENARIOS = scenario_module.SCENARIOS
    scenario_ids = list(SCENARIOS.keys())

    # 2. Prepare the tasks (Chunks of scenario IDs + Seed combinations)
    tasks = []
    for i in range(0, len(scenario_ids), args.chunk_size):
        chunk = scenario_ids[i : i + args.chunk_size]
        for seed in range(1, args.seeds + 1):
            tasks.append((args.scenario_file, chunk, seed))

    total_tasks = len(tasks)
    print(
        f"Prepared {total_tasks} chunks (Chunks of {args.chunk_size} across {args.seeds} seeds)."
    )
    print(
        f"Starting execution with {args.workers} parallel workers calling HPC_main.py...\n"
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.output_file)), exist_ok=True)

    # 3. Execute subprocesses in parallel and aggregate stdout locally
    completed = 0

    # Note: We use ThreadPoolExecutor instead of ProcessPoolExecutor because threading
    # is much more efficient for waiting on completely separate CLI subprocesses.
    with open(args.output_file, "w") as f:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(run_hpc_main, *task): task for task in tasks}

            for future in as_completed(futures):
                f.write(future.result())
                f.flush()  # Ensure it writes to disk immediately
                completed += 1
                print(
                    f"\rProgress: {completed}/{total_tasks} ({(completed/total_tasks)*100:.1f}%) complete.",
                    end="",
                )

    print(f"\n\nAll tasks complete. Results saved to {args.output_file}")
