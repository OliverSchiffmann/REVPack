import copy

dict_default = {
    "description": "Standard run with default parameters",
    "main": {
        "simulation_years": 15,
        "time_unit": "day",  # length of one step: "day", "week" or "month"
        "B2B_population": 1000,
        "B2C_population": 0,
        "seed": 1,
        "enable_reman": True,
        "starting_customers": 0,
    },
    "oem": {
        # Financial & Core Storage
        "balance": 0.0,
        "location": "Brescia",
        "virgin_stock": 50,
        "reman_stock": 0,
        "core_stock": 5,
        "core_storage_limit": 100,
        "unit_production_cost_V": 500.0,
        "retail_price_V": 1000,
        "retail_price_R": 1000,
        # Reman Implementation, grouping these together as i can imagine these being the main levers that are pulled from an oem perspective
        "reman_implementation_cost": 10000.0,  # One off to buy inspection equipment and such
        "reman_annual_operating_cost": 5000.0,  # Fixed annual costs for reman production
        "unit_production_cost_R": 300.0,
        # Production: "make_to_order" (make what waiting customers ask for) or
        # "make_to_stock" (reman from every accepted core, virgin only for orders the
        # stock can't cover; customers take whatever is in stock, reman first)
        "production_policy": "make_to_order",
        # Processing Rates
        "delivery_delay": 3,
        "manufacture_delay": 5,
        "remanufacture_delay": 4,
        "core_acceptance_rate": 0.7,
        # Logistics & Processing Costs
        "core_collection_cost": 20,
        "core_disposal_cost": 10,
        "core_storage_cost": 2,
        "inspection_cost": 20,
        # Heuristic Routing Logistics
        "routing_heuristics": False,  # True also needs local_delivery_cost, shipping_cost_per_km, ferry_fee, driving_hours_per_day
        # Core collection strategies (T5.3), keyed by name. Values are rough
        # placeholders until agreed with partners.
        "collection_strategies": {
            "buy_back": {
                "enabled": False,
                "bounty_value": 10.0,  # EUR paid per accepted core (assumed)
                "return_rate_uplift": 0.1,  # added to core_return_rate (assumed)
                "setup_cost": 0.0,  # EUR one-off: legal, IT, training, marketing (assumed)
            },
            "lease": {
                "enabled": False,
                "lease_period": 12,  # model months of 28 days (assumed)
                "monthly_fee_V": 70.0,  # EUR per month (assumed)
                "monthly_fee_R": 55.0,  # EUR per month (assumed)
                "acceptance_uplift": 0.15,  # added to core_acceptance_rate (assumed)
                "collection_cost_saving": 0.25,  # share of core_collection_cost saved (assumed)
                "setup_cost": 0.0,  # EUR one-off: legal, IT, training, marketing (assumed)
            },
        },
    },
    "b2b_customer": {
        "patience": 10,
        "mean_lifetime": 500,
        "lifetime_method": "triangular",
        "lifetime_range": 100,
        "lifetime_shape": 4.0,  # Weibull wear-out shape (weibull method only)
        "early_failure_share": 0.035,  # share of near-instant failures (weibull method only)
        "core_return_rate": 0.8,
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
            "demand_profile": {"type": "stochastic", "rate": 0.0006},
            "wom_threshold": 0.015,
        },
        "R": {
            "demand_profile": {"type": "stochastic", "rate": 0.0003},
            "wom_threshold": 0.015,
            "cores_consumed": 1,
        },
    },
}

dict_buy_back = copy.deepcopy(dict_default)
dict_buy_back["description"] = "Buy-back: owners are paid for each accepted core"
dict_buy_back["oem"]["collection_strategies"]["buy_back"]["enabled"] = True

dict_lease = copy.deepcopy(dict_default)
dict_lease["description"] = (
    "Lease: every customer leases, products come back at lease end"
)
dict_lease["oem"]["collection_strategies"]["lease"]["enabled"] = True

dict_no_reman = copy.deepcopy(dict_default)
dict_no_reman["description"] = "Run with remanufacturing disabled"
dict_no_reman["main"]["enable_reman"] = False

# Advertising rates calibrated from Simplan forecast files (synthetic OS data).
# Stores file paths, not loaded data: the files are only opened when this
# scenario is run, so importing this module (e.g. in the webapp) never needs them.
dict_forecast = copy.deepcopy(dict_default)
dict_forecast["description"] = (
    "Advertising rates calibrated from example Simplan forecasts (synthetic OS data)"
)
dict_forecast["main"]["simulation_years"] = 5
dict_forecast["main"][
    "time_unit"
] = "day"  # must match the forecast files' frequency (daily)
dict_forecast["main"][
    "B2B_population"
] = 1000  # market size the example data was made for
dict_forecast["main"]["B2C_population"] = 0
dict_forecast["main"]["starting_customers"] = 200
dict_forecast["products"]["V"]["demand_profile"] = {
    "type": "forecast",
    "forecast": "examples/forecasts/forecast_virgin.json",
}
dict_forecast["products"]["R"]["demand_profile"] = {
    "type": "forecast",
    "forecast": "examples/forecasts/forecast_reman.json",
}

SCENARIOS = {
    "Default": dict_default,
    "No Reman": dict_no_reman,
    "Buy-back": dict_buy_back,
    "Lease": dict_lease,
    "Forecast": dict_forecast,
}
