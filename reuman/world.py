"""
Module for the World agent.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from ._agent import AgentEnum, BaseAgent
import random
from .message import Message
import asyncio
from . import customer
from .product import ProductEnum
import copy
from . import demand_inputs
from .model_time_converter import ModelTimeConverter
from collections.abc import Sequence

if TYPE_CHECKING:
    from .customer import Customer, CustomerStatesEnum
    from .OEM import OEM


class World:
    """
    World agent.

    The World agent is the backbone of the simulation, managing the clock, agents, and global state tracking. It allows for the communication between agents and stores the properties of the simulation world.

    """

    _now: int
    _agents: dict[int, BaseAgent]
    _agents_by_type: dict[AgentEnum, list[int]]
    _num_potential_users: int
    _num_wants: dict[ProductEnum, int]
    _num_uses: dict[ProductEnum, int]
    _num_wants_any: int
    _message_queue: list[Message]
    _active_products: list[ProductEnum]
    _config: dict
    _demand_profiles: dict
    _demand_calibration: dict
    _new_customers_today: dict[ProductEnum, int]
    _time_converter: ModelTimeConverter

    def __init__(self, config: dict) -> None:
        """
        Initialise the World agent.

        Args:
            config (dict): The global configuration dictionary.
        """

        self._now = 0
        self._agents = {}
        self._agents_by_type = {AgentEnum.CUSTOMER: [], AgentEnum.OEM: []}
        self._num_potential_users = 0
        self._num_wants = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._num_uses = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._num_wants_any = 0
        self._new_customers_today = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._message_queue = []
        self._active_products = [ProductEnum.V]
        self._config = config

        # One converter per run: turns real-world units (days, years) into steps
        self._time_converter = ModelTimeConverter.from_config(config)

        if config["main"]["enable_reman"]:
            self._active_products.append(ProductEnum.R)

        # Work on a copy of the demand profiles so the caller's config is never changed
        self._demand_profiles = {
            key: copy.deepcopy(product_data["demand_profile"])
            for key, product_data in config["products"].items()
        }

        # Preload a deterministic demand CSV (new customers per day) so it isn't read during the run
        for profile in self._demand_profiles.values():
            if profile["type"] != "deterministic":
                continue
            val = profile["amount_per_day"]

            if isinstance(val, str):
                try:
                    import csv

                    loaded_vals = []
                    with open(val, "r", encoding="utf-8") as f:
                        reader = csv.reader(f)
                        for row in reader:
                            if row:
                                try:
                                    loaded_vals.append(int(float(row[0])))
                                except ValueError:
                                    pass  # Skip headers or non-numeric rows
                    profile["amount_per_day"] = loaded_vals
                except Exception as e:
                    raise RuntimeError(f"Failed to load demand CSV '{val}': {e}") from e
        # Hand-entered profiles are per day: convert them to per step
        self._convert_profiles_to_steps()

        # Turn any forecast profiles into stochastic rates (runs once, before the simulation).
        # Must come after the conversion above: forecast rates are estimated per step
        # already, and converting them again would count the step length twice.
        self._demand_calibration = self._resolve_forecast_profiles()

    # leading underscore (_) infront of function is used to indicate it is only to be called in __init__

    def _convert_profiles_to_steps(self) -> None:
        """
        Convert hand-entered demand profiles from per-day values to per-step values.

        Stochastic rates (probability per day) become probabilities per step.
        Deterministic amounts (customers per day) become customers per step and
        are stored under "amount_per_step"; a list (e.g. from a daily sales CSV)
        holds one value per day and is added up per step. Forecast profiles are
        left alone.
        """
        tc = self._time_converter
        for profile in self._demand_profiles.values():
            if profile["type"] == "stochastic":
                rate = profile["rate"]
                if not isinstance(rate, (int, float)):
                    raise ValueError(
                        "A stochastic demand rate must be a single number (probability per day). "
                        f"Received: {rate!r}. For daily sales data use a deterministic profile."
                    )
                profile["rate"] = tc.daily_prob_to_step_prob(rate)
            elif profile["type"] == "deterministic":
                amount = profile.pop("amount_per_day")
                if isinstance(amount, list):
                    profile["amount_per_step"] = tc.daily_amounts_to_step_amounts(
                        amount
                    )
                else:
                    profile["amount_per_step"] = tc.per_day_to_per_step(amount)

    def _resolve_forecast_profiles(self) -> dict:
        """
        Replace every demand profile of type "forecast" with a stochastic rate
        estimated from the forecast data. V and R are estimated together because
        they share one pool of potential customers.

        Returns:
            dict: Calibration details per product ("V"/"R"), empty if no forecasts.
        """
        forecast_keys = [
            key
            for key, profile in self._demand_profiles.items()
            if profile["type"] == "forecast"
        ]
        if not forecast_keys:
            return {}

        if "R" in forecast_keys and not self._config["main"]["enable_reman"]:
            raise ValueError(
                "A reman forecast was supplied but remanufacturing is disabled. "
                "Enable remanufacturing or remove the R forecast."
            )

        series = {}
        for key in forecast_keys:
            data = self._demand_profiles[key].get("forecast")
            if data is None:
                raise ValueError(
                    f"Product {key} has a forecast demand profile but no forecast data."
                )
            # The forecast must have one value per model step (e.g. weekly for weekly steps)
            frequency = self._time_converter.frequency
            if isinstance(data, str):  # a file path (Python scripts)
                data = demand_inputs.load_forecast_file(data, frequency)
            else:  # already-parsed data (webapp)
                demand_inputs.validate_forecast(data, frequency)
            series[key] = demand_inputs.build_forecast_series(data, frequency)

        main = self._config["main"]
        rates = demand_inputs.estimate_ad_rates(
            series.get("V"),
            series.get("R"),
            market_size=main["B2B_population"] + main["B2C_population"],
            starting_customers=main["starting_customers"],
        )

        calibration = {}
        for key, rate in rates.items():
            s = series[key]
            self._demand_profiles[key] = {"type": "stochastic", "rate": rate}
            calibration[key] = {
                "rate": rate,
                "start_date": s.dates[0].isoformat(),
                "end_date": s.dates[-1].isoformat(),
                "history_days": s.history_days,
                "clipped_days": s.clipped_days,
                "values": list(s.values),
            }
        return calibration

    def get_demand_calibration(self) -> dict:
        """
        Returns a copy of the forecast calibration details (empty if no forecasts were used).

        Returns:
            dict: Per product: rate, start/end dates, history days, clipped days, daily values.
        """
        return copy.deepcopy(self._demand_calibration)

    def tick(self) -> None:
        """
        Moves the simulation on to the next time step and updates the stored states of the customers.
        """

        self._now += 1
        self.update_customer_state_counts()

    def time_converter(self) -> ModelTimeConverter:
        """
        Returns the converter between real-world units and model steps for this run.

        Returns:
            ModelTimeConverter: The run's time converter.
        """
        return self._time_converter

    def now(self) -> int:
        """
        Returns the current time step of the simulation.

        Returns:
            int: The current time step.
        """
        return self._now

    def get_agents(self) -> list[BaseAgent]:
        """
        Returns a list of all agents currently in the simulation.

        Returns:
            list[BaseAgent]: A list of all agents.
        """
        return list(self._agents.values())

    def get_active_products(self) -> list[ProductEnum]:
        """
        Returns a copy of the list of active products in the simulation.

        Returns:
            list[ProductEnum]: A copy of the list of active products.
        """
        return self._active_products[:]  # returns a copy to avoid editing

    def add_agent(self, agent: BaseAgent):
        """
        Adds an agent to the simulation world.

        Args:
            agent (BaseAgent): The agent to be added.
        """
        if agent.id() in self._agents:
            exit(f"Agent with id already exists. Received: {agent.id}")
        self._agents[agent.id()] = agent
        self._agents_by_type[agent.type()].append(agent.id())

    def add_agents_from_list(self, agents: Sequence[BaseAgent]):
        """
        Adds a list of agents to the simulation world.

        Args:
            agents (list[BaseAgent]): A list of agents to be added.
        """

        for agent in agents:
            self.add_agent(agent)

    def generate_demand(self, rng):
        """
        Calculates this step's demand based on global product configurations and
        forcefully transitions selected POTENTIAL_USERs into the market.
        """
        from .customer import CustomerStatesEnum

        self._new_customers_today = {product: 0 for product in ProductEnum}

        potential_users = [
            agent
            for agent in self._agents.values()
            if agent.type() == AgentEnum.CUSTOMER
            and agent.state() == CustomerStatesEnum.POTENTIAL_USER
        ]

        if not potential_users:
            return

        products_to_consider = self.get_active_products()
        rng.shuffle(products_to_consider)

        for product in products_to_consider:
            profile = self._demand_profiles[product.name]
            profile_type = profile["type"]

            if profile_type == "stochastic":
                num_to_enter = rng.binomial(len(potential_users), profile["rate"])
            elif profile_type == "deterministic":
                amount = profile["amount_per_step"]

                if isinstance(amount, list):
                    # _now is 1 on the first simulated step, so we subtract 1 for the 0-based list index
                    idx = self._now - 1
                    if 0 <= idx < len(amount):
                        num_to_enter = amount[idx]
                    else:
                        num_to_enter = 0  # Default to 0 if the simulation runs longer than the list
                else:
                    num_to_enter = amount

            num_to_enter = min(num_to_enter, len(potential_users))
            self._new_customers_today[product] = max(0, int(num_to_enter))

            if num_to_enter > 0:
                picked_indices = rng.choice(
                    len(potential_users), size=num_to_enter, replace=False
                )
                # Sort descending so we can safely pop them out of the list
                for idx in sorted(picked_indices, reverse=True):
                    agent = potential_users.pop(idx)
                    agent.force_market_entry(rng, product)  # type: ignore

    def call_next(self, rng):
        """
        Calls the next function for each of the agents in the simulation.

        Args:
            rng (numpy.random.Generator): Random number generator.
        """

        # Call OEM agents first (as they were originally added first)
        for oem_id in self._agents_by_type[AgentEnum.OEM]:
            self._agents[oem_id].next(rng)

        # Shuffle customer agents to prevent ordering bias for limited stock
        customer_ids = self._agents_by_type[AgentEnum.CUSTOMER][:]
        rng.shuffle(customer_ids)
        for cust_id in customer_ids:
            self._agents[cust_id].next(rng)

    def update_customer_state_counts(self):
        """
        Updates the counts for all the customer states in the simulation.
        """

        from .customer import CustomerStatesEnum

        self._num_wants = {product: 0 for product in ProductEnum}
        self._num_uses = {product: 0 for product in ProductEnum}
        self._num_wants_any = 0
        self._num_waiting_for_delivery = 0
        potential_users = 0

        for agent in self._agents.values():
            if isinstance(agent, customer.Customer):
                if agent.state() == CustomerStatesEnum.POTENTIAL_USER:
                    potential_users += 1
                elif agent.state() == CustomerStatesEnum.WANTS_VIRGIN:
                    self._num_wants[ProductEnum.V] += 1
                elif agent.state() == CustomerStatesEnum.USES_VIRGIN:
                    self._num_uses[ProductEnum.V] += 1
                elif agent.state() == CustomerStatesEnum.WANTS_REMAN:
                    self._num_wants[ProductEnum.R] += 1
                elif agent.state() == CustomerStatesEnum.USES_REMAN:
                    self._num_uses[ProductEnum.R] += 1
                elif agent.state() == CustomerStatesEnum.WANTS_ANY:
                    self._num_wants_any += 1
                elif agent.state() == CustomerStatesEnum.WAITING_FOR_DELIVERY:
                    self._num_waiting_for_delivery += 1

        self._num_potential_users = potential_users

    def receive_message(self, message: Message):
        """
        Adds a message to the message queue.

        Args:
            message (Message): The message to be added.
        """

        self._message_queue.append(message)

    def process_messages(self, rng):
        """
        Deals with all of the messages in the queue. Sending them to the appropriate agent and telling that agent to process the message.

        Args:
            rng (numpy.random.Generator): Random number generator.
        """

        for message in self._message_queue:
            recipient = self._agents.get(message.recipient_id)
            if recipient:
                recipient.handle_message(message, rng)
        self._message_queue.clear()

    async def run(self, rng, n_steps: int, progress_callback=None) -> tuple[dict, dict]:
        """
        Executes the simulation loop for a specified number of steps,
        collects time-series results, and generates a final report.

        Args:
            rng (numpy.random.Generator): Seeded random number generator.
            n_steps (int): Number of steps to simulate (see ModelTimeConverter.years_to_steps).
            progress_callback: Optional function called with (step, n_steps) for progress bars.
        """
        # Find the OEM agent for data collection
        oem_id = self._agents_by_type[AgentEnum.OEM][0]
        oemAgent: OEM = self._agents[oem_id]  # type: ignore

        results = {
            "step": [],
            "day": [],
            "potential_users": [],
            "wants_virgin": [],
            "uses_virgin": [],
            "wants_reman": [],
            "uses_reman": [],
            "wants_any": [],
            "waiting_for_delivery": [],
            "core_stock": [],
            "virgin_stock": [],
            "reman_stock": [],
            "virgin_sold": [],
            "reman_sold": [],
            "cores_collected": [],
            "cores_rejected": [],
            "inspection_cost": [],
            "bounty_values_paid": [],
            "oem_balance": [],
            "new_customers_V": [],
            "new_customers_R": [],
        }

        for i in range(n_steps):
            self.tick()

            # Record states
            results["step"].append(self.now())
            results["day"].append(self._time_converter.step_to_day(self.now()))
            results["potential_users"].append(self._num_potential_users)
            results["wants_virgin"].append(self._num_wants[ProductEnum.V])
            results["uses_virgin"].append(self._num_uses[ProductEnum.V])
            results["wants_reman"].append(self._num_wants[ProductEnum.R])
            results["uses_reman"].append(self._num_uses[ProductEnum.R])
            results["wants_any"].append(self._num_wants_any)
            results["waiting_for_delivery"].append(self._num_waiting_for_delivery)

            # Fetch OEM specific data cleanly
            oem_metrics = oemAgent.get_tracking_metrics()
            for key, value in oem_metrics.items():
                results[key].append(value)

            self.generate_demand(rng)
            # Recorded after generate_demand so each value belongs to the same day
            results["new_customers_V"].append(self._new_customers_today[ProductEnum.V])
            results["new_customers_R"].append(self._new_customers_today[ProductEnum.R])
            self.call_next(rng)

            if progress_callback is not None:
                update_interval = max(1, n_steps // 100)
                if i % update_interval == 0:
                    progress_callback(i, n_steps)
                    await asyncio.sleep(0)

        report = oemAgent.generate_financial_report()
        return results, report
