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

def lhs_categorical(choices, num_samples):
    """
    Generates Latin Hypercube samples mapped to discrete categories or booleans.

    Args:
        choices (list): A list of possible categorical values or booleans.
        num_samples (int): Number of samples to generate.

    Returns:
        list: A list of sampled choices.
    """
    # Generate standard continuous LHS between 0 and 1
    base_lhs = lhs_numeric(0, 1, num_samples, is_int=False)
    samples = []
    
    for val in base_lhs:
        # Map the [0, 1) value to an index in the choices list
        idx = int(val * len(choices))
        # Failsafe for floating point edge cases (e.g., exactly 1.0)
        idx = min(idx, len(choices) - 1)
        samples.append(choices[idx])
        
    return samples

# --- 2. Define Parameters and Run LHS ---

# Set exactly how many scenarios you want in your sweep
NUM_SCENARIOS = 50

# Generate the independent LHS arrays for each parameter
sweep_data = {
    # Continuous/Integer ranges (min, max, samples, is_int)
    "simulation_length": lhs_numeric(1000, 2000, NUM_SCENARIOS, is_int=True),
    "BtoB_population": lhs_numeric(50, 200, NUM_SCENARIOS, is_int=True),
    "manufacture_delay": lhs_numeric(2, 10, NUM_SCENARIOS, is_int=True),
    "core_acceptance_rate": lhs_numeric(0.3, 0.9, NUM_SCENARIOS, is_int=False),
    "patience": lhs_numeric(5, 20, NUM_SCENARIOS, is_int=True),
    
    # Categorical/Boolean choices
    "enable_reman": lhs_categorical([True, False], NUM_SCENARIOS)
}

all_scenarios = {}

# --- 3. Construct the Nested Dictionary Output ---

for i in range(NUM_SCENARIOS):
    scenario_id = i + 1
    all_scenarios[scenario_id] = {
        "description": f"Scenario {scenario_id}",
        "main": {
            "simulation_length": sweep_data["simulation_length"][i],
            "BtoB_population": sweep_data["BtoB_population"][i],
            "seed": 1, 
            "enable_reman": sweep_data["enable_reman"][i],
        },
        "oem": {
            "manufacture_delay": sweep_data["manufacture_delay"][i],
            "remanufacture_delay": 3,
            "virgin_stock": 10,
            "unit_production_cost_V": 1000.0,
            "unit_production_cost_R": 200.0,
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