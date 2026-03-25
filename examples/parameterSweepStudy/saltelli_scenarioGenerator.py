
import pprint
import numpy as np
from SALib.sample import sobol

# 1. Import the problem from another file, so that its consistent across scenario generation and the analysis file
from problemBounds import problem


if __name__ == "__main__":

    # --- 2. Generate Saltelli Samples ---
    # N is the baseline sample size. Typically 512, 1024, or 2048.
    N = 2048
    
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
                "manufacture_delay": 5, #int(round(row[0])),
                "remanufacture_delay": 5, #int(round(row[1])),
                "virgin_stock": 10,
                "unit_production_cost_V": int(round(row[0])),
                "unit_production_cost_R": int(round(row[1])),
                "core_acceptance_rate": round(row[4], 2), # Float rounded
                "core_collection_cost": 20, 
                "core_disposal_cost": 15,
                "retail_price_V": int(round(row[3])),
                "retail_price_R": int(round(row[4])),
            },
            "b2b_customer": {
                "patience": 10, #int(round(row[5])),
                "mean_lifetime": 55,
            },
            "b2c_customer": {
                "patience": 10, #int(round(row[5])),
                "mean_lifetime": 55,
            },
        }

    # --- 4. Save to .py ---
    output_filename = "examples/parameterSweepStudy/saltelli_parameters_v2.py"
    with open(output_filename, "w") as f:
        f.write("import numpy as np \n")
        f.write("SCENARIOS = " + pprint.pformat(all_scenarios, indent=4))

    print(f"Successfully generated {total_scenarios} Saltelli scenarios and saved to '{output_filename}'.")