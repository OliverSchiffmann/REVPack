import copy

dict_default = {
    "description": "Standard run for unit testing",
    "main": {
        "simulation_length": 1000,
        "B2B_population": 10,
        "B2C_population": 10,
        "seed": 42,
        "enable_reman": True,
        "starting_customers": 0,
    },
    "oem": {
        "balance": 0.0,
        "location": "Brescia",
        "distance_matrix": None,
        "virgin_stock": 10,
        "reman_stock": 0,
        "core_stock": 0,
        "core_storage_limit": 100,
        "bounty_value": 10.0,
        "unit_production_cost_V": 500.0,
        "unit_production_cost_R": 300.0,
        "retail_price_V": 1000.0,
        "retail_price_R": 900.0,
        "delivery_delay": 1,
        "manufacture_delay": 5,
        "remanufacture_delay": 4,
        "core_acceptance_rate": 1.0,
        "core_collection_cost": 20.0,
        "core_disposal_cost": 20.0,
        "core_storage_cost": 2.0,
        "inspection_cost": 0.0,
        "local_delivery_cost": 10.0,
        "shipping_cost_per_km": 0.01,
        "ferry_fee": 10.0,
        "driving_hours_per_day": 8.0,
    },
    "b2b_customer": {
        "patience": 10,
        "mean_lifetime": 200,
        "lifetime_method": "triangular",
        "lifetime_range": 50,
        "core_return_rate": 1.0,
    },
    "b2c_customer": {
        "patience": -1,
        "mean_lifetime": 50,
        "lifetime_method": "uniform",
        "lifetime_range": 3,
        "core_return_rate": 1.0,
    },
    "products": {
        "V": {
            "advertising_effectiveness": 0.0006,
            "wom_threshold": 0.015,
        },
        "R": {
            "advertising_effectiveness": 0.0003,
            "wom_threshold": 0.015,
            "cores_consumed": 1,
        },
    }
}

TEST_SCENARIOS = {
    "Default": dict_default
}