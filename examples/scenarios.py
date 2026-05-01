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
            # Financial & Core Storage
            "balance": 0.0,
            "location": "Brescia",
            "virgin_stock": 10,
            "reman_stock": 0,
            "core_stock": 0, 
            "core_storage_limit": 100,
            "bounty_value": 10.0,
            "unit_production_cost_V": 500.0,
            "unit_production_cost_R": 300.0,
            "retail_price_V": 1000,
            "retail_price_R": 1000,
            
            # Processing Rates
            "delivery_delay": 3, 
            "manufacture_delay": 5, 
            "remanufacture_delay": 4,
            "core_acceptance_rate": 1.0,
            
            # Logistics & Processing Costs
            "core_collection_cost": 20, 
            "core_disposal_cost": 20, 
            "core_storage_cost": 2, 
            "inspection_cost": 0.0,
            
            # Heuristic Routing Logistics (New)
            "local_delivery_cost": 10.0,
            "shipping_cost_per_km": 0.01,
            "ferry_fee": 10.0,
            "driving_hours_per_day": 8.0,
        },
        "b2b_customer": {
            "patience": 10,
            "mean_lifetime": 200, 
            "lifetime_method": "triangular",
            "lifetime_range": 100,
            "core_return_rate": 1.0,

        },
        "b2c_customer": {
            "patience": -1,
            "mean_lifetime": 1,
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
                "cores_consumed": 2,
        },
        }
    }

dict_no_reman = copy.deepcopy(dict_default)
dict_no_reman["description"] = "Run with remanufacturing disabled"
dict_no_reman["main"]["enable_reman"] = False

SCENARIOS = {
    "Default": dict_default,
    "No Reman": dict_no_reman,
}
