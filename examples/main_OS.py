import argparse
import matplotlib.pyplot as plt
import importlib.util
import os
import asyncio

from examples.simulation_runner import run_simulation

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Economic Feasibility Model")
    # Tells you where to pull the scenario dictionary from
    parser.add_argument(
        "--scenario_file",
        type=str,
        default="examples/scenarios.py",
        help="Name of the scenario file to pull 'SCENARIOS' dict from",
    )
    # Chooses which scenario to get the config values from, all the scenarios are based off of 'Default' anyway
    parser.add_argument(
        "--scenario", type=str, default="Default", help="Number of the scenario to run"
    )
    # Defaults to plotting the output results, if you add the argument then it won't plot
    parser.add_argument(
        "--no_plot", action="store_true", help="Do you want to plot the results?"
    )
    # Defines the seed that random will use to run the sim
    parser.add_argument(
        "--seed", type=int, default=None, help="Random seed for reproducibility"
    )
    args = parser.parse_args()

    # Import the SCENARIOS dictionary from the specified file

    # Check if the scenario file exists at the specified path
    if not os.path.exists(args.scenario_file):
        raise FileNotFoundError(f"Scenario file '{args.scenario_file}' not found.")

    # Load the scenario from the provided file path, treating it as a python module
    spec = importlib.util.spec_from_file_location("scenario_module", args.scenario_file)
    if spec and spec.loader:
        scenario_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scenario_module)
        # Ensure the module contains the 'SCENARIOS' dict
        if hasattr(scenario_module, "SCENARIOS"):
            SCENARIOS = scenario_module.SCENARIOS
        else:
            raise AttributeError(
                f"The file '{args.scenario_file}' does not contain a 'SCENARIOS' dictionary."
            )
    else:
        raise ImportError(f"Could not load scenario file '{args.scenario_file}'.")

    # Validate that the requested scenario key exists in the dictionary
    if args.scenario not in SCENARIOS:
        raise ValueError(
            f"Scenario '{args.scenario}' not found. Options are: {list(SCENARIOS.keys())}"
        )

    # Defines the config from the chosen scenario
    config = SCENARIOS[args.scenario]
    print("-" * 40)
    print(f"Running Scenario: {args.scenario}")
    print(f"Description: {config['description']}")
    print("-" * 40)

    # Run the extracted simulation logic
    results, report = asyncio.run(run_simulation(config, args.seed))

    cost = report["Total Cost"]
    revenue = report["Total Revenue"]
    profit = revenue - cost

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

    if not args.no_plot:
        fig, (ax1, ax2, ax3) = plt.subplots(
            nrows=3, ncols=1, sharex=True, figsize=(10, 8)
        )

        colours = [
            "#2fa8e9",  # Potential Users (Light Blue)
            "#fb9a99",  # Wants Virgin (Light Red)
            "#d91c1f",  # Uses Virgin (Dark Red)
            "#bce499",  # Wants Reman (Light Green)
            "#33a02c",  # Uses Reman (Dark Green)
            "#D1AB23",  # Wants any
            "#F200FF",  # Waiting for delivery
        ]

        ax1.stackplot(
            results["day"],
            results["potential_users"],
            results["wants_virgin"],
            results["uses_virgin"],
            results["wants_reman"],
            results["uses_reman"],
            results["wants_any"],
            results["waiting_for_delivery"],
            labels=[
                "Potential Users",
                "Wants Virgin",
                "Uses Virgin",
                "Wants Reman",
                "Uses Reman",
                "Wants Any",
                "Waiting for Delivery",
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
