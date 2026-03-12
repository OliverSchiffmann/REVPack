import argparse
from scenarios import SCENARIOS
from reuman.world import World
from reuman._agent import AgentEnum
from reuman.customer import Customer, CustomerStatesEnum
from reuman.product import ProductEnum
from reuman.OEM import OEM
from numpy import random
import matplotlib.pyplot as plt

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Economic Feasibility Model")
    parser.add_argument(
        "--scenario", type=str, default="Default", help="Name of the scenario to run"
    )
    args = parser.parse_args()

    if args.scenario not in SCENARIOS:
        raise ValueError(
            f"Scenario '{args.scenario}' not found. Options are: {list(SCENARIOS.keys())}"
        )

    config = SCENARIOS[args.scenario]
    print("-" * 40)
    print(f"Running Scenario: {args.scenario}")
    print(f"Description: {config['description']}")
    print("-" * 40)

    rng = random.default_rng(seed=config["main"]["seed"])
    world = World(
        enable_reman=config["main"]["enable_reman"]
    )  # Toggle reman on/off with True/False

    BtoB_population: int = config["main"]["BtoB_population"]
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

    for i in range(0, BtoB_population):
        customer = Customer(id=i, world=world, oem=oemAgent, config=config["customer"])
        world.add_agent(customer)

    for i in range(0, simulation_length):  # model time unit is days
        world.tick()
        # print(f"---------")
        # print(f"Day {world.now()}:\n")

        # print(
        #     f"Potential users: {world._num_potential_users},\n Wanting Virgin: {world._num_wants[ProductEnum.V]}, Using Virgin: {world._num_uses[ProductEnum.V]}\n Wanting Reman: {world._num_wants[ProductEnum.R]}, Using Reman: {world._num_uses[ProductEnum.R]}\n"
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
