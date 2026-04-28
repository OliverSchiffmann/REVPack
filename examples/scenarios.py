import copy

dict_default = {
    "description": "Standard run with default parameters",
    "main": {
        "simulation_length": 1000,
        "B2B_population": 1000,
        "B2C_population": 0,
        "seed": 1,
        "enable_reman": True,
        "starting_customers": 100,
    },
    "oem": {
        "delivery_delay": 3,  # Doesn't change much, however also the potential to introduce local/national/international distribution?
        "manufacture_delay": 5,  # Really no idea
        "remanufacture_delay": 4,  # Depends on reman method
        "virgin_stock": 50,
        "reman_stock": 0,
        "core_stock": 10,
        "unit_production_cost_V": 500.0,  # Euros very approximately
        "unit_production_cost_R": 300.0,  # Depends on the reman method
        "core_acceptance_rate": 0.7,  # Depends on the reman method, fraction of usable cores produced from the returned ones
        "core_collection_cost": 20,  # No idea, also local/national/international
        "core_disposal_cost": 20,  # No idea
        "core_storage_cost": 2,  # Storage cost per core per day
        "retail_price_V": 1000,  # Likewise Euros approx
        "retail_price_R": 900,  # In theory the same since reman is good as new or better?
    },
    "b2b_customer": {
        "patience": 10,
        "mean_lifetime": 200,  # AC's last for 10 or so years, how long is the sim meant to be?
        "lifetime_method": "triangular",
        "lifetime_range": 100,
        "core_return_rate": 1.0,
    },
    "b2c_customer": {
        "patience": -1,
        "mean_lifetime": 1,
        "lifetime_method": "uniform",
        "lifetime_range": 3,
    },
    "products": {
        "V": {
            "advertising_effectiveness": 0.0006,
            "wom_threshold": 0.015,
        },
        "R": {
            "advertising_effectiveness": 0.0003,
            "wom_threshold": 0.015,
            "cores_consumed": 2,
        },
    },
}

dict_no_reman = copy.deepcopy(dict_default)
dict_no_reman["description"] = "Run with remanufacturing disabled"
dict_no_reman["main"]["enable_reman"] = False

SCENARIOS = {
    "Default": dict_default,
    "No Reman": dict_no_reman,
}
