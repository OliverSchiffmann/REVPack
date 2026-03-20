import argparse
# from examples.parameterSweepStudy.lhs_parameter_sweep import SCENARIOS
# from scenarios import SCENARIOS
from reuman.world import World
from reuman._agent import AgentEnum
from reuman.customer import B2B_Customer, B2C_Customer, CustomerStatesEnum
from reuman.product import ProductEnum
from reuman.OEM import OEM
from numpy import random
import matplotlib.pyplot as plt
import importlib.util
import os, json

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Economic Feasibility Model")
    parser.add_argument(
        "--scenario_file", type=str, default="examples/scenarios.py", help="Name of the scenario file to pull 'SCENARIOS' dict from",
    )
    parser.add_argument(
        "--scenario", type=str, default="Default", help="Number of the scenario to run"
    )
    # Defaults to plotting the output results, if you add the argument then it won't plot
    parser.add_argument(
        "--no_plot", action="store_true", help="Do you want to plot the results?"
    )
    parser.add_argument(
        "--json_output", action="store_true", help="Do you want the output as a json?"
    )
    args = parser.parse_args()
    
    # Import the SCENARIOS dictionary from the specified file

    # Check if the scenario file exists at the specified path
    if not os.path.exists(args.scenario_file):
        raise FileNotFoundError(f"Scenario file '{args.scenario_file}' not found.")

    # Load the scenario from the provided file path as a python module
    spec = importlib.util.spec_from_file_location("scenario_module", args.scenario_file)
    if spec and spec.loader:
        scenario_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scenario_module)
        # Ensure the module contains the 'SCENARIOS' dict
        if hasattr(scenario_module, "SCENARIOS"):
            SCENARIOS = scenario_module.SCENARIOS
        else:
            raise AttributeError(f"The file '{args.scenario_file}' does not contain a 'SCENARIOS' dictionary.")
    else:
        raise ImportError(f"Could not load scenario file '{args.scenario_file}'.")

    # Validate that the requested scenario key exists in the dictionary
    if args.scenario not in SCENARIOS:
        raise ValueError(
            f"Scenario '{args.scenario}' not found. Options are: {list(SCENARIOS.keys())}"
        )

    config = SCENARIOS[args.scenario]
    print("-" * 40)
    print(f"Running Scenario: {args.scenario}")
    print(f"Description: {config['description']}")
    print("-" * 40)

    # rng = random.default_rng(seed=config["main"]["seed"])
    rng = random.default_rng()
    world = World(
        enable_reman=config["main"]["enable_reman"]
    )  # Toggle reman on/off with True/False

    B2B_population: int = config["main"]["B2B_population"]
    B2C_population: int = config["main"]["B2C_population"]
    simulation_length: int = config["main"][
        "simulation_length"
    ]  # number of DAYS the simulation runs for

    results = {
        "day": [],
        "potential_users": [],
        "wants_virgin": [],
        "uses_virgin": [],
        "wants_reman": [],
        "uses_reman": [],
        "wants_any": [],
        "core_stock": [],
        "virgin_stock": [],
        "reman_stock": [],
        "virgin_sold": [],
        "reman_sold": [],
        "cores_collected": [],
        "cores_rejected": [],
    }

    oemAgent = OEM(id=-1, world=world, config=config["oem"])
    world.add_agent(oemAgent)

    ids = 1
    
    for i in range(0, B2B_population):
        b2b_customer = B2B_Customer(id=ids, world=world, oem=oemAgent, config=config["b2b_customer"])
        world.add_agent(b2b_customer)
        ids += 1
        
    for i in range(0, B2C_population):
        b2c_customer = B2C_Customer(id=ids, world=world, oem=oemAgent, config=config["b2c_customer"])
        world.add_agent(b2c_customer)
        ids += 1


    for i in range(0, simulation_length):  # model time unit is days
        world.tick()
        # print(f"---------")
        # print(f"Day {world.now()}:\n")

        # print(
        #     f"Potential users: {world._num_potential_users},\n Wanting Virgin: {world._num_wants[ProductEnum.V]}, Using Virgin: {world._num_uses[ProductEnum.V]}\n Wanting Reman: {world._num_wants[ProductEnum.R]}, Using Reman: {world._num_uses[ProductEnum.R]}\n, Want Any: {world._num_wants_any}"
        # )

        results["day"].append(world.now())
        results["potential_users"].append(world._num_potential_users)
        results["wants_virgin"].append(world._num_wants[ProductEnum.V])
        results["uses_virgin"].append(world._num_uses[ProductEnum.V])
        results["wants_reman"].append(world._num_wants[ProductEnum.R])
        results["uses_reman"].append(world._num_uses[ProductEnum.R])
        results["wants_any"].append(world._num_wants_any)
        results["core_stock"].append(oemAgent._core_stock)
        results["virgin_stock"].append(oemAgent._factory_stock[ProductEnum.V])
        results["reman_stock"].append(oemAgent._factory_stock[ProductEnum.R])
        results["virgin_sold"].append(oemAgent._products_sold[ProductEnum.V])
        results["reman_sold"].append(oemAgent._products_sold[ProductEnum.R])
        results["cores_collected"].append(oemAgent._total_cores_collected)
        results["cores_rejected"].append(oemAgent._total_cores_rejected)

        world.call_next(rng)

    report = oemAgent.generate_financial_report()
    cost = report["Total Cost"]
    revenue = report["Total Revenue"]
    profit = revenue - cost

    if not args.json_output:
        print("\nCost Breakdown:")
        for key, value in report["Breakdown"].items():
            print(f"  {key}: €{value:,.2f}")

        print("\nOperational Stats:")
        for key, value in report["Statistics"].items():
            print(f"  {key}: {value:,.0f}")
        print("\n")
        print("-" * 40)
        print(f"{'FINANCIAL SUMMARY':^40}")
        print("-" * 40)

        print(f"Total Cost (€):      -{cost:,.2f}")
        print(f"Total Revenue (€):   +{revenue:,.2f}")
        print("-" * 40)
        print(f"NET PROFIT (€):      {profit:+,.2f}")
        print("-" * 40)

    else:
        print("JSON_START")

        # Unwrap the report to be a single dictionary so it neatly goes into the output csv
        report_json = report["Breakdown"]
        report_json.update(report["Statistics"])
        report_json["Cost"] = cost
        report_json["Revenue"] = revenue
        report_json["Profit"] = profit

        print(json.dumps(report_json))


    if not args.no_plot:
        fig, (ax1, ax2, ax3) = plt.subplots(nrows=3, ncols=1, sharex=True, figsize=(10, 8))

        colours = [
            "#2fa8e9",  # Potential Users (Light Blue)
            "#fb9a99",  # Wants Virgin (Light Red)
            "#d91c1f",  # Uses Virgin (Dark Red)
            "#bce499",  # Wants Reman (Light Green)
            "#33a02c",  # Uses Reman (Dark Green)
            "#D1AB23",  # Wants any
        ]

        ax1.stackplot(
            results["day"],
            results["potential_users"],
            results["wants_virgin"],
            results["uses_virgin"],
            results["wants_reman"],
            results["uses_reman"],
            results["wants_any"],
            labels=[
                "Potential Users",
                "Wants Virgin",
                "Uses Virgin",
                "Wants Reman",
                "Uses Reman",
                "Wants Any",
            ],
            colors=colours,
        )

        ax1.set_title("Customer States Over Time")
        ax1.set_ylabel("Number of Customers")
        ax1.legend(loc="lower left")
        ax1.grid(True, alpha=0.3)

        ax2.plot(
            results["day"],
            results["core_stock"],
            color="#807E7E",
            linewidth=2,
            label="Core Stock",
        )
        ax2.plot(
            results["day"],
            results["virgin_stock"],
            color=colours[2],
            linewidth=2,
            label="Virgin Stock",
        )
        ax2.plot(
            results["day"],
            results["reman_stock"],
            color=colours[4],
            linewidth=2,
            label="Reman Stock",
        )

        ax2.set_title("OEM Inventory Level")
        ax2.set_ylabel("Units")
        ax2.legend(loc="upper right")
        ax2.grid(True, alpha=0.3)

        ax3.plot(
            results["day"],
            results["virgin_sold"],
            color=colours[2],
            linewidth=2,
            label="Virgin Sold",
        )

        ax3.plot(
            results["day"],
            results["reman_sold"],
            color=colours[4],
            linewidth=2,
            label="Reman Sold",
        )

        ax3.plot(
            results["day"],
            results["cores_collected"],
            color=colours[3],
            linewidth=2,
            label="Cores Collected",
        )

        ax3.plot(
            results["day"],
            results["cores_rejected"],
            color=colours[1],
            linewidth=2,
            label="Cores Rejected",
        )

        ax3.set_xlabel("Day")
        ax3.set_title("Sales and Reverse Logistics")
        ax3.set_ylabel("Units")
        ax3.legend(loc="upper left")
        ax3.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()
