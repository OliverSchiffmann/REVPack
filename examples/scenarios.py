import copy

dict_default = {
        "description": "Standard run with default parameters",
        "main": {
            "simulation_length": 365*20,
            "B2B_population": 1000,
            "B2C_population": 0,
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
            "unit_production_cost_R": 300.0,
            "core_acceptance_rate": 0.6,
            "core_collection_cost": 20,
            "core_disposal_cost": 20,
            "retail_price_V": 1000, # Likewise Euros approx
            "retail_price_R": 1000,
        },
        "b2b_customer": {
            "patience": 10,
            "mean_lifetime": 0.7*365, 
            "lifetime_method": "weibull",
            "lifetime_range": 3,
            "core_return_rate": 0.5,
        },
        "b2c_customer": {
            "patience": -1,
            "mean_lifetime": 1,
            "lifetime_method": "uniform",
            "lifetime_range": 3,
        },
    }

dict_no_reman = copy.deepcopy(dict_default)
dict_no_reman["description"] = "Run with remanufacturing disabled"
dict_no_reman["main"]["enable_reman"] = False

SCENARIOS = {
    "Default": dict_default,
    "No Reman": dict_no_reman,
}