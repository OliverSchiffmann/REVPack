import csv
import json
from numpy import random
from reuman.world import World
from reuman.product import ProductEnum
from reuman.OEM import OEM
from reuman.customer import B2B_Customer, B2C_Customer


async def run_simulation(config, seed=None, progress_callback=None):
    """Runs the simulation given a config dictionary and returns the results arrays and report."""
    if seed is not None:
        rng = random.default_rng(seed=seed)
    else:
        rng = random.default_rng(config["main"]["seed"])

    world = World(config=config)

    B2B_population: int = config["main"]["B2B_population"]
    B2C_population: int = config["main"]["B2C_population"]
    simulation_length: int = config["main"]["simulation_length"]

    # Load geographic data
    cities = []
    probabilities = []
    city_coords = {}
    with open("examples/locations/it.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            city_name = row["city"]
            cities.append(city_name)
            city_coords[city_name] = {
                "lat": float(row["lat"]),
                "lng": float(row["lng"]),
            }
            prob = row.get("probability")
            if prob is not None:
                probabilities.append(float(prob))
            else:
                probabilities.append(1.0)
        probabilities[-1] = 1.0 - sum(
            probabilities[:-1]
        )  # To avoid precision float errors summing > 1.0

    with open("examples/locations/italy_100x100_matrix.json", "r") as f:
        distance_matrix = json.load(f)

    config["oem"]["location"] = "Brescia"
    config["oem"]["distance_matrix"] = distance_matrix

    oemAgent = OEM(id=-1, world=world, config=config)
    world.add_agent(oemAgent)

    idIterator = 1
    customer_agents = []

    customer_counts_by_city = {city: 0 for city in cities}
    if not cities:
        customer_counts_by_city["Rome"] = 0

    for id_ in range(idIterator, idIterator + B2B_population):
        loc = rng.choice(cities, p=probabilities) if cities else "Rome"
        customer_counts_by_city[loc] += 1
        customer_agents.append(
            B2B_Customer(
                id=id_,
                world=world,
                oem=oemAgent,
                config=config,
                location=loc,
            )
        )
    idIterator += B2B_population

    for id_ in range(idIterator, idIterator + B2C_population):
        loc = rng.choice(cities, p=probabilities) if cities else "Rome"
        customer_counts_by_city[loc] += 1
        customer_agents.append(
            B2C_Customer(
                id=id_,
                world=world,
                oem=oemAgent,
                config=config,
                location=loc,
            )
        )
    idIterator += B2C_population

    world.add_agents_from_list(customer_agents)

    starting_customers = config["main"]["starting_customers"]
    if starting_customers > 0:
        indices = rng.choice(
            len(customer_agents),
            size=min(starting_customers, len(customer_agents)),
            replace=False,
        )
        for idx in indices:
            customer_agents[idx].initialise_as_active_user(rng, ProductEnum.V)

    # Delegate execution to the World agent
    results, report = await world.run(rng, simulation_length, progress_callback)

    # Package the geographic data into the report for the webapp overlay
    report["Geographic Distribution"] = {
        "OEM Location": config["oem"]["location"],
        "City Data": {},
    }
    for city, count in customer_counts_by_city.items():
        if count > 0 or city == config["oem"]["location"]:
            report["Geographic Distribution"]["City Data"][city] = {
                "lat": city_coords.get(city, {"lat": 0.0})["lat"],
                "lng": city_coords.get(city, {"lng": 0.0})["lng"],
                "customers": count,
                "is_oem": city == config["oem"]["location"],
            }

    return results, report
