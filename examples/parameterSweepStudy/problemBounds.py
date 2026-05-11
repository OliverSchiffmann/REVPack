
"""
Dictionary to reliably define the the `problem' between the Sobol sampling then analysis.
"""
problem_dict = {
        'remanufacture_delay': [1, 10],      # remanufacture_delay
        'unit_production_cost_R': [200, 500],    # unit_production_cost_R
        'core_acceptance_rate': [0.0, 1.0],   # core_acceptance_rate (Float)
        'core_return_rate': [0.0, 1.0],
        'cores_consumed': [1, 10],
        'core_storage_limit': [50, 500],
    }

problem = {
    'num_vars': len(problem_dict),
    'names': list(problem_dict.keys()),
    'bounds': list(problem_dict.values()),
}