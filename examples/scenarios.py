SCENARIOS = {
    "Default": {
        "description": "Standard run with default parameters",
        "main": {
            "simulation_length": 1200,
            "B2B_population": 50,
            "B2C_population": 50,
            "seed": 1,
            "enable_reman": True,
        },
        "oem": {
            "delivery_delay": 1,
            "manufacture_delay": 5,
            "remanufacture_delay": 3,
            "virgin_stock": 10,
            "reman_stock": 0,
            "core_stock": 0,
            "unit_production_cost_V": 500.0, # Euros very approximately
            "unit_production_cost_R": 200.0,
            "core_acceptance_rate": 0.7,
            "core_collection_cost": 5,
            "core_disposal_cost": 20,
            "retail_price_V": 1000, # Likewise Euros approx
            "retail_price_R": 1000,
        },
        "b2b_customer": {
            "patience": -1,
            "mean_lifetime": 55, 
        },
        "b2c_customer": {
            "patience": -1,
            "mean_lifetime": 55,
        },
    },
    "Default_no_reman": {
        "description": "Standard run with default parameters",
        "main": {
            "simulation_length": 1200,
            "B2B_population": 100,
            "seed": 1,
            "enable_reman": False,
        },
        "oem": {
            "manufacture_delay": 5,
            "remanufacture_delay": 3,
            "virgin_stock": 10,
            "unit_production_cost_V": 1000.0,
            "unit_production_cost_R": 200.0,
            "core_acceptance_rate": 0.7,
            "core_collection_cost": 40,
            "core_disposal_cost": 20,
            "retail_price_V": 1200,
            "retail_price_R": 900,
        },
        "b2b_customer": {
            "patience": 10,
            "mean_lifetime": 20 
        },
    },
}
