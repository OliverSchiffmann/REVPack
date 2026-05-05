
"""
Dictionary to reliably define the the `problem' between the Sobol sampling then analysis.
"""
problem_dict = {
        # 'manufacture_delay': [1, 10],      # manufacture_delay
        'remanufacture_delay': [1, 10],      # remanufacture_delay
        # 'unit_production_cost_V': [200, 500],    # unit_production_cost_V
        'unit_production_cost_R': [200, 500],    # unit_production_cost_R
        'core_acceptance_rate': [0.0, 1.0],   # core_acceptance_rate (Float)
        'core_return_rate': [0.0, 1.0],
        # 'patience': [0, 20],      # patience 
        'mean_lifetime': [100, 500],     # mean_lifetime
        # 'core_collection_cost': [1, 100],     # core_collection_cost
        # 'core_disposal_cost': [1, 100],     # core_disposal_cost
        # 'retail_price_V': [500, 2000],  # retail_price_V
        # 'retail_price_R': [500, 2000],   # retail_price_R
        'cores_consumed': [1, 10],
        'core_storage_limit': [50, 500],
    }

problem = {
    'num_vars': len(problem_dict),
    'names': list(problem_dict.keys()),
    'bounds': list(problem_dict.values()),
}