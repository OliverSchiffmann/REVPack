import pprint
import numpy as np
import copy

# 1. Import the problem from another file
from examples.parameterSweepStudy.problemBounds import problem
# Import the baseline scenario to use as a template
from examples.scenarios import SCENARIOS

if __name__ == "__main__":

    # Mapping to robustly find where parameters belong in the scenario config
    # This handles deeply nested dictionaries like 'products' -> 'R'
    PARAM_MAPPING = {
        'remanufacture_delay': ['oem'],
        'unit_production_cost_R': ['oem'],
        'core_acceptance_rate': ['oem'],
        'core_return_rate': ['b2b_customer'],
        'cores_consumed': ['products', 'R'],
        'core_storage_limit': ['oem']
    }

    # --- 2. OFAT Configuration ---
    # Number of points to sample across the bounds of each parameter
    samples_per_param = 50 
    
    total_scenarios = len(problem['names']) * samples_per_param
    print(f"Generating {total_scenarios} OFAT scenarios (sweeping {len(problem['names'])} parameters with {samples_per_param} steps each)...")

    # --- 3. Construct the Dictionary Output ---
    all_scenarios = {}
    
    # Optionally, save the pure baseline as the very first scenario for easy reference
    baseline_scenario = copy.deepcopy(SCENARIOS['Default'])
    baseline_scenario["description"] = "Baseline Scenario (All nominal values)"
    all_scenarios["baseline"] = baseline_scenario

    scenario_counter = 1

    # Loop through one parameter at a time
    for var_idx, var_name in enumerate(problem['names']):
        
        # Get the min and max bounds for this specific parameter
        min_val, max_val = problem['bounds'][var_idx]
        
        # Generate evenly spaced values between min and max
        sweep_values = np.linspace(min_val, max_val, samples_per_param)

        target_path = PARAM_MAPPING.get(var_name)
        if not target_path:
            print(f"Warning: Parameter '{var_name}' not found in PARAM_MAPPING. Skipping.")
            continue

        for val in sweep_values:
            # Start with a fresh deep copy of the Default baseline scenario
            # This ensures ALL OTHER parameters remain at their default values
            new_scenario = copy.deepcopy(SCENARIOS['Default'])

            # Apply rounding/casting: floats for rates, ints for costs/delays/patience
            if any(x in var_name for x in ['rate', 'probability', 'factor']):
                val_formatted = round(float(val), 4)
            else:
                val_formatted = int(round(val))

            # Name the scenario so it's easy to identify during analysis
            scenario_id = f"{scenario_counter}"
            new_scenario["description"] = f"OFAT Sweep: {var_name} = {val_formatted}"

            # Traverse to the correct nested dictionary and update the value
            target_dict = new_scenario
            for key in target_path[:-1]:
                target_dict = target_dict.setdefault(key, {})
            target_dict[target_path[-1]] = val_formatted

            all_scenarios[scenario_id] = new_scenario
            scenario_counter += 1

    # --- 4. Save to .py ---
    output_filename = "examples/parameterSweepStudy/ofat_parameters_v2.py"
    with open(output_filename, "w") as f:
        f.write("import numpy as np \n\n")
        f.write("# Generated OFAT Scenarios\n")
        f.write("SCENARIOS = " + pprint.pformat(all_scenarios, indent=4))

    print(f"Successfully generated {scenario_counter - 1} OFAT scenarios + 1 baseline and saved to '{output_filename}'.")