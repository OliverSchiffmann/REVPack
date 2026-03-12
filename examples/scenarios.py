SCENARIOS = {
    "Default": {
        "description": "Standard run with default parameters",
        "main": {
            "simulation_length": 1200,
            "BtoB_population": 100,
            "seed": 1,
            "enable_reman": True,
        },
        "oem": {
            "manufacture_delay": 5,
            "remanufacture_delay": 3,
            "virgin_stock": 10,
            "unit_production_cost_V": 1000.0,
            "unit_production_cost_R": 200.0,
            "core_acceptance_rate": 0.7,
        },
        "customer": {
            "patience": 10,
        },
    },
    "Default_no_reman": {
        "description": "Standard run with default parameters",
        "main": {
            "simulation_length": 1200,
            "BtoB_population": 100,
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
        },
        "customer": {
            "patience": 10,
        },
    },
}
