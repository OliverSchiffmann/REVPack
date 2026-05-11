import argparse
import importlib.util
import os
import sys
import asyncio
import json

# Import the simulation runner logic
from examples.simulation_runner import run_simulation

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Generic HPC Batch Simulation")
    parser.add_argument("--scenario_file", type=str, required=True, help="Scenario dictionary file")
    parser.add_argument("--scenario", type=str, required=True, help="Scenario ID to run")
    parser.add_argument("--seed", type=int, default=1, help="Random seed for reproducibility")
    args = parser.parse_args()
    
    # 1. Load the scenario config
    if not os.path.exists(args.scenario_file):
        print(f"Error: Scenario file '{args.scenario_file}' not found.")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("scenario_module", args.scenario_file)
    if spec is None or spec.loader is None:
        print(f"Error: Could not load spec for '{args.scenario_file}'.")
        sys.exit(1)
    scenario_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenario_module)
    
    if not hasattr(scenario_module, "SCENARIOS"):
        print(f"Error: '{args.scenario_file}' does not contain a 'SCENARIOS' dictionary.")
        sys.exit(1)
        
    SCENARIOS = scenario_module.SCENARIOS
    if args.scenario not in SCENARIOS:
        print(f"Error: Scenario '{args.scenario}' not found.")
        sys.exit(1)

    config = SCENARIOS[args.scenario]
    
    # 2. Run the simulation core
    results, report = asyncio.run(run_simulation(config, args.seed))

    # 3. Output results directly as a JSON payload
    output_data = {
        "metadata": {
            "Scenario": args.scenario,
            "Seed": args.seed
        },
        "report": report
    }
    
    # Print with a distinct prefix so it can be easily grabbed from stdout log files
    print(f"HPC_JSON_RESULT::{json.dumps(output_data)}")
