
import pprint
import numpy as np
from SALib.sample import sobol

if __name__ == "__main__":

    # --- 1. Define the SALib Problem ---
    problem_dict = {
        'manufacture_delay': [1, 10],      # manufacture_delay
        'remanufacture_delay': [1, 10],      # remanufacture_delay
        'unit_production_cost_V': [1, 1000],    # unit_production_cost_V
        'unit_production_cost_R': [1, 1000],    # unit_production_cost_R
        'core_acceptance_rate': [0.0, 1.0],   # core_acceptance_rate (Float)
        'patience': [1, 20],      # patience
        'mean_lifetime': [5, 100],     # mean_lifetime
        'core_collection_cost': [1, 100],     # core_collection_cost
        'core_disposal_cost': [1, 100],     # core_disposal_cost
        'retail_price_V': [500, 2000],  # retail_price_V
        'retail_price_R': [500, 2000],   # retail_price_R
    }

    problem = {
        'num_vars': len(problem_dict),
        'names': list(problem_dict.keys()),
        'bounds': list(problem_dict.values()),
    }

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
        
        # SALib outputs numpy floats. We must cast the integer variables back to ints.
        # We use round() before int() to avoid floor truncation issues (e.g., 9.999 -> 9).
        all_scenarios[scenario_id] = {
            "description": f"Scenario {scenario_id}",
            "main": {
                "simulation_length": 1200,
                "B2B_population": 50,
                "B2C_population": 50,
                "enable_reman": True,
            },
            "oem": {
                # The values from the row must correspond to their position in the problem dictionary.
                "manufacture_delay": int(round(row[0])),
                "remanufacture_delay": int(round(row[1])),
                "virgin_stock": 10,
                "unit_production_cost_V": int(round(row[2])),
                "unit_production_cost_R": int(round(row[3])),
                "core_acceptance_rate": round(row[4], 3), # Float rounded
                "core_collection_cost": 20, 
                "core_disposal_cost": 15,
                "retail_price_V": int(round(row[6])),
                "retail_price_R": int(round(row[7])),
            },
            "b2b_customer": {
                "patience": int(round(row[5])),
                "mean_lifetime": 55,
            },
            "b2c_customer": {
                "patience": int(round(row[5])),
                "mean_lifetime": 55,
            },
        }

    # --- 4. Save to .py ---
    output_filename = "examples/parameterSweepStudy/saltelli_parameters.py"
    with open(output_filename, "w") as f:
        f.write("import numpy as np \n")
        f.write("SCENARIOS = " + pprint.pformat(all_scenarios, indent=4))

    print(f"Successfully generated {total_scenarios} Saltelli scenarios and saved to '{output_filename}'.")