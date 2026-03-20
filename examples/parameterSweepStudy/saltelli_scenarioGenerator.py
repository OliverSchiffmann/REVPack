
import pprint
import numpy as np
from SALib.sample import sobol

if __name__ == "__main__":

    # --- 1. Define the SALib Problem ---
    # Note: 'seed' is removed. We only want parameters that drive systemic behaviour.
    problem = {
        'num_vars': 8,
        'names': [
            'manufacture_delay', 
            'remanufacture_delay', 
            'unit_production_cost_V', 
            'unit_production_cost_R', 
            'core_acceptance_rate', 
            'patience', 
            # 'mean_lifetime', 
            # 'core_collection_cost', 
            # 'core_disposal_cost', 
            'retail_price_V', 
            'retail_price_R'
        ],
        # Bounds MUST match the order of the names above
        'bounds': [
            [1, 10],      # manufacture_delay
            [1, 10],      # remanufacture_delay
            [1, 1000],    # unit_production_cost_V
            [1, 1000],    # unit_production_cost_R
            [0.0, 1.0],   # core_acceptance_rate (Float)
            [1, 20],      # patience
            # [5, 100],     # mean_lifetime
            # [1, 100],     # core_collection_cost
            # [1, 100],     # core_disposal_cost
            [500, 2000],  # retail_price_V
            [500, 2000]   # retail_price_R
        ]
    }

    # --- 2. Generate Saltelli Samples ---
    # N is the baseline sample size. Typically 512, 1024, or 2048.
    # Total scenarios = N * (2 * num_vars + 2)
    # E.g. for N=1024 and 12 vars: 1024 * (24 + 2) = 26624 scenarios
    N = 1024 
    param_values = sobol.sample(problem, N)
    
    total_scenarios = len(param_values)
    print(f"Generating {total_scenarios} scenarios based on N={N}...")

    # --- 3. Construct the Nested Dictionary Output ---
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
                "seed": int(round(row[0])), # Run multiple seeds in your simulation loop, not the sampler!
                "enable_reman": True,
            },
            "oem": {
                "manufacture_delay": int(round(row[0])),
                "remanufacture_delay": int(round(row[1])),
                "virgin_stock": 10,
                "unit_production_cost_V": int(round(row[2])),
                "unit_production_cost_R": int(round(row[3])),
                "core_acceptance_rate": round(row[4], 3), # Float, rounded for neatness
                "core_collection_cost": 20, # int(round(row[8])),
                "core_disposal_cost": 15, # int(round(row[9])),
                "retail_price_V": int(round(row[6])),
                "retail_price_R": int(round(row[7])),
            },
            "b2b_customer": {
                "patience": int(round(row[5])),
                "mean_lifetime": 55, #int(round(row[7])),
            },
            "b2c_customer": {
                "patience": int(round(row[5])),
                "mean_lifetime": 55, #int(round(row[7])),
            },
        }

    # --- 4. Save to .py ---
    output_filename = "examples/parameterSweepStudy/saltelli_parameters.py"
    with open(output_filename, "w") as f:
        f.write("import numpy as np \n")
        f.write("SCENARIOS = " + pprint.pformat(all_scenarios, indent=4))

    print(f"Successfully generated {total_scenarios} Saltelli scenarios and saved to '{output_filename}'.")