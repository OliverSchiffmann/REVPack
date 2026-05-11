import pprint
import numpy as np
import copy
from SALib.sample import sobol

# 1. Import the problem from another file, so that its consistent across scenario generation and the analysis file
from examples.parameterSweepStudy.problemBounds import problem

# Import the baseline scenario to use as a template
from examples.scenarios import SCENARIOS

if __name__ == "__main__":

    # Define where each parameter belongs in the scenario config dictionary
    PARAM_MAPPING = {
        "remanufacture_delay": ["oem"],
        "unit_production_cost_R": ["oem"],
        "core_acceptance_rate": ["oem"],
        "core_return_rate": ["b2b_customer"],
        "mean_lifetime": ["b2b_customer"],
        "cores_consumed": [
            "products",
            "R",
        ],  # Use 'X': ['Y', 'Z'] to represent config['X']['Y']['Z'], e.g. config['products']['R']['cores_consumed']
        "core_storage_limit": ["oem"],
    }

    # --- 2. Generate Saltelli Samples ---
    # N is the baseline sample size. Typically 512, 1024, or 2048.
    N = 1024

    # Where the sampled values are actually generated
    param_values = sobol.sample(problem, N)

    total_scenarios = len(param_values)

    # Shows you how many total scenarios were created for your number of samples and variables
    print(f"Generating {total_scenarios} scenarios based on N={N}...")

    # Knits the varied samples into the static ones from the default scenarios dict
    all_scenarios = {}

    for i, row in enumerate(param_values):
        scenario_id = f"{i + 1}"

        # Start with a copy of the Default scenario
        new_scenario = copy.deepcopy(SCENARIOS["Default"])
        new_scenario["description"] = f"Scenario {scenario_id}"

        # Map the sampled row values to the scenario structure based on problem['names']
        for var_idx, var_name in enumerate(problem["names"]):
            val = row[var_idx]
            # Apply rounding/casting: floats for rates, ints for costs/delays/patience
            if any(x in var_name for x in ["rate", "probability", "factor"]):
                val = round(float(val), 4)
            else:
                val = int(round(val))

            # Force the new value into the correct agent configuration block(s)
            target_paths = PARAM_MAPPING.get(var_name)
            if not target_paths:
                # If a parameter from the problem is not in the mapping, skip it.
                # This prevents accidentally adding it to the wrong place.
                print(
                    f"Warning: Parameter '{var_name}' from problem definition is not in PARAM_MAPPING. Skipping."
                )
                continue

            if target_paths and isinstance(target_paths[0], str):
                target_paths = [target_paths]

            for path in target_paths:
                target_dict = new_scenario
                for key in path:
                    target_dict = target_dict.setdefault(key, {})
                target_dict[var_name] = val

        all_scenarios[scenario_id] = new_scenario

    # Save the output in the usual format
    output_filename = "examples/parameterSweepStudy/saltelli_parameters_6_5.py"
    with open(output_filename, "w") as f:
        f.write("import numpy as np \n")
        f.write("SCENARIOS = " + pprint.pformat(all_scenarios, indent=4))

    print(
        f"Successfully generated {total_scenarios} Saltelli scenarios and saved to '{output_filename}'."
    )
