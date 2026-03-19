from SALib.analyze import sobol
import pandas as pd
 
problem = {
    'num_vars': 11,
    'names': [
        'manufacture_delay', 
        'remanufacture_delay', 
        'unit_production_cost_V', 
        'unit_production_cost_R', 
        'core_acceptance_rate', 
        'patience', 
        'mean_lifetime', 
        'core_collection_cost', 
        'core_disposal_cost', 
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
        [5, 100],     # mean_lifetime
        [1, 100],     # core_collection_cost
        [1, 100],     # core_disposal_cost
        [500, 2000],  # retail_price_V
        [500, 2000]   # retail_price_R
    ]
}

HPCResults = pd.read_csv("examples/parameterSweepStudy/saltelli_outputs.csv")

Si = sobol.analyze(problem, HPCResults["Profit"].to_numpy(), print_to_console=True)