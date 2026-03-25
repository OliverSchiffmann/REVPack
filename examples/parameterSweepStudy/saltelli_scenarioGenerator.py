import pprint
import numpy as np
import copy
from SALib.sample import sobol

# 1. Import the problem from another file, so that its consistent across scenario generation and the analysis file
from problemBounds import problem
# Import the baseline scenario to use as a template
from examples.scenarios import SCENARIOS


if __name__ == "__main__":

    # --- 2. Generate Saltelli Samples ---
    # N is the baseline sample size. Typically 512, 1024, or 2048.
    N = 1024
    
    param_values = sobol.sample(problem, N)
    
    total_scenarios = len(param_values)
    print(f"Generating {total_scenarios} scenarios based on N={N}...")

    # --- 3. Construct the Dictionary Output ---
    all_scenarios = {}

    for i, row in enumerate(param_values):
        scenario_id = f"{i + 1}"

        # Start with a deep copy of the Default scenario
        new_scenario = copy.deepcopy(SCENARIOS['Default'])
        new_scenario["description"] = f"Scenario {scenario_id}"

        # Map the sampled row values to the scenario structure based on problem['names']
        for var_idx, var_name in enumerate(problem['names']):
            val = row[var_idx]
            # Apply rounding/casting: floats for rates, ints for costs/delays/patience
            if any(x in var_name for x in ['rate', 'probability', 'factor']):
                val = round(float(val), 4)
            else:
                val = int(round(val))

            # Update the value in the nested dictionary if the key exists
            for category in ["main", "oem", "b2b_customer", "b2c_customer"]:
                if var_name in new_scenario.get(category, {}):
                    new_scenario[category][var_name] = val

        all_scenarios[scenario_id] = new_scenario

    # --- 4. Save to .py ---
    output_filename = "examples/parameterSweepStudy/saltelli_parameters_v3.py"
    with open(output_filename, "w") as f:
        f.write("import numpy as np \n")
        f.write("SCENARIOS = " + pprint.pformat(all_scenarios, indent=4))

    print(f"Successfully generated {total_scenarios} Saltelli scenarios and saved to '{output_filename}'.")