import random
import pprint

# --- 1. Helper Functions for Native LHS ---

def lhs_numeric(min_val, max_val, num_samples, is_int=False):
    """
    Generates Latin Hypercube samples for a continuous or integer range.

    Args:
        min_val (float): The lower bound of the range.
        max_val (float): The upper bound of the range.
        num_samples (int): Number of samples to generate.
        is_int (bool, optional): If True, rounds samples to the nearest integer. Defaults to False.

    Returns:
        list: A shuffled list of sampled values.
    """
    step = (max_val - min_val) / num_samples
    samples = []
    
    for i in range(num_samples):
        # Pick a random point within the specific interval [i*step, (i+1)*step]
        val = random.uniform(min_val + i * step, min_val + (i + 1) * step)
        
        if is_int:
            # Round to nearest integer if required
            samples.append(int(round(val)))
        else:
            # Round floats to 3 decimal places for cleaner JSON outputs
            samples.append(round(val, 3))
            
    # Shuffle the samples to randomize how they pair with other parameters
    random.shuffle(samples)
    return samples

# --- 2. Define Parameters and Run LHS ---
if __name__ == "__main__":

    # Set exactly how many scenarios you want in your sweep
    NUM_SCENARIOS = 1000

    # Generate the independent LHS arrays for each parameter
    sweep_data = {
        # Continuous/Integer ranges (min, max, samples, is_int)
        'manufacture_delay':lhs_numeric(1,10, NUM_SCENARIOS, is_int=True),
        'remanufacture_delay':lhs_numeric(1,10, NUM_SCENARIOS, is_int=True),
        'unit_production_cost_V':lhs_numeric(1, 10000, NUM_SCENARIOS, is_int=True),
        'unit_production_cost_R':lhs_numeric(1, 10000, NUM_SCENARIOS, is_int=True),
        'core_acceptance_rate':lhs_numeric(0, 1, NUM_SCENARIOS, is_int=False),
        'patience':lhs_numeric(1, 10, NUM_SCENARIOS, is_int=True),
    }

    all_scenarios = {}

    # --- 3. Construct the Nested Dictionary Output ---

    for i in range(NUM_SCENARIOS):
        scenario_id = f"{i + 1}"
        all_scenarios[scenario_id] = {
            "description": f"Scenario {scenario_id}",
            "main": {
                "simulation_length": 1200,
                "BtoB_population": 100,
                "seed": 1, 
                "enable_reman": True,
            },
            "oem": {
                "manufacture_delay": sweep_data["manufacture_delay"][i],
                "remanufacture_delay": sweep_data["remanufacture_delay"][i],
                "virgin_stock": 10,
                "unit_production_cost_V": sweep_data["unit_production_cost_V"][i],
                "unit_production_cost_R": sweep_data["unit_production_cost_R"][i],
                "core_acceptance_rate": sweep_data["core_acceptance_rate"][i],
            },
            "customer": {
                "patience": sweep_data["patience"][i],
            },
        }

    # --- 4. Save to .py ---

    output_filename = "examples/parameterSweepStudy/lhs_parameters.py"
    with open(output_filename, "w") as f:
        f.write("SCENARIOS = " + pprint.pformat(all_scenarios, indent=4))

    print(f"Successfully generated {NUM_SCENARIOS} LHS scenarios and saved to '{output_filename}'.")