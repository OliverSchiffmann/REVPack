from ydata_profiling import ProfileReport
import pandas as pd
import os
import importlib.util
   
   
HPCResults = pd.read_csv("examples/parameterSweepStudy/saltelli_outputs_1_5.csv")

# Group by scenario and calculate the mean to average out the seeds
HPCResults = HPCResults.groupby("Scenario", as_index=False).mean()

scenarios = "examples/parameterSweepStudy/saltelli_parameters_1_5.py"

# Load the SCENARIOS dictionary (Update the path below if the filename differs)
scenario_file = "examples/parameterSweepStudy/scenarios.py"
if not os.path.exists(scenario_file):
    scenario_file = "examples/scenarios.py"
    
spec = importlib.util.spec_from_file_location("scenario_module", scenarios)
scenario_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scenario_module)
SCENARIOS = scenario_module.SCENARIOS

# Flatten the specific target nested parameters into a list of simple dictionaries
scenario_params = []
for scen_id, config in SCENARIOS.items():
    scenario_params.append({
        "Scenario": int(scen_id),
        "remanufacture_delay": config['oem']['remanufacture_delay'],
        "unit_production_cost_R": config['oem']['unit_production_cost_R'],
        "core_acceptance_rate": config['oem']['core_acceptance_rate'],
        "core_return_rate": config['b2b_customer']['core_return_rate'],
        "mean_lifetime": config['b2b_customer']['mean_lifetime'],
        "cores_consumed": config['products']['R']['cores_consumed'],
        "core_storage_limit": config['oem']['core_storage_limit']
    })
    
# Convert to DataFrame and merge directly into HPCResults
params_df = pd.DataFrame(scenario_params)
HPCResults = HPCResults.merge(params_df, on="Scenario", how="left")

# Generate a profile report to investigate the raw simulation outputs
print("Generating data profile report for raw HPC results...")
profile = ProfileReport(HPCResults, title="Profiling Report for Sobol Input Data")
profile.to_file("sobol_input_data_profile.html")
print("Data profile report saved to 'sobol_input_data_profile.html'.")
