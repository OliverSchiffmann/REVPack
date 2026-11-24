"""
Module for the Original Equipment Manufacturer (OEM) agent.
"""

from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING, NamedTuple
from ._agent import AgentEnum, BaseAgent
from .message import Message, MessageType
from .product import ProductEnum, ProductDetails, product_params
from .customer import Customer, CustomerStatesEnum
from .states import OEMStatesEnum
from .collection_strategies import (
    CollectionStrategy,
    Contract,
    ContractKind,
    build_strategies,
)

if TYPE_CHECKING:
    from .world import World


class IncomingCore(NamedTuple):
    """A core in transit back to the OEM."""

    arrival_step: int
    location: str | None
    contract: Contract | None  # the terms the product was held on


class OEM(BaseAgent):
    """
    Original Equipment Manufacturer (OEM) agent.

    The OEM produces the virgin or reman product for the customers, processes the reman cores manages its own stock and production rates.
    """

    _state: OEMStatesEnum
    _balance: float
    _delivery_delay_steps: int  # 0 means delivered within the step
    _manufacture_delay_steps: int  # >= 1: production divides by it
    _remanufacture_delay_steps: int  # >= 1: production divides by it
    _factory_stock: dict[ProductEnum, float]  # stock of products
    _production_rate: dict[ProductEnum, float]
    _products_sold: dict[ProductEnum, int]
    _sale_revenue: dict[ProductEnum, float]  # revenue actually booked at sale
    _total_products_produced: dict[ProductEnum, float]
    _num_to_man: dict[ProductEnum, float]
    _core_stock: float  # initial stock of cores for remanufacturing
    _core_acceptance_rate: float
    _total_cores_collected: int
    _total_cores_rejected: int
    _total_cores_not_collected: int
    _total_cores_over_capacity: int
    _unit_production_cost_V: float
    _unit_production_cost_R: float
    _core_collection_cost: float
    _core_disposal_cost: float
    _core_storage_cost_per_step: float
    _total_core_storage_cost: float
    _core_storage_limit: int
    _total_acquisition_cost: float  # paid to customers for accepted cores
    _retail_price_V: float
    _retail_price_R: float
    _inspection_cost: float
    _total_inspection_costs: float
    _incoming_cores: list[IncomingCore]
    _config: dict
    _reman_implementation_cost: float
    _reman_operating_cost_per_step: float
    _total_reman_operating_cost: float
    _reman_enabled: bool
    _routing_enabled: bool
    _strategies: list[CollectionStrategy]
    _total_contract_fees: float

    def __init__(self, id: int, world: World, config: dict) -> None:
        """
        Initialise the OEM agent.

        Args:
            id (int): Unique id for the agent.
            world (World): The simulation world the agent belongs to.
            config (dict): Configuration dictionary containing the OEM's parameters.

        Raises:
            ValueError: If manufacture_delay or remanufacture_delay is less than 1 day.
            ValueError: if cores consumed is not a positive number greater than 0.
            ValueError: if the old oem.bounty_value setting is present.
        """
        self._config = config
        oem_config = config["oem"]
        if oem_config["manufacture_delay"] < 1:
            raise ValueError(
                f"manufacture_delay must be >=1 day. Received: {oem_config['manufacture_delay']}"
            )
        if oem_config["remanufacture_delay"] < 1:
            raise ValueError(
                f"remanufacture_delay must be >=1 day. Received: {oem_config['remanufacture_delay']}"
            )
        cores_consumed = config["products"]["R"]["cores_consumed"]
        if cores_consumed <= 0:
            raise ValueError(f"cores_consumed must be >0. Received: {cores_consumed}")
        if "bounty_value" in oem_config:
            raise ValueError(
                "oem.bounty_value is no longer used: the bounty is now the 'buy_back' "
                "collection strategy. Remove bounty_value and set "
                "oem.collection_strategies.buy_back = {'enabled': True, "
                "'bounty_value': ..., 'return_rate_uplift': ...}."
            )

        super().__init__(id=id, type=AgentEnum.OEM, world=world)

        self._balance = oem_config["balance"]

        self._state = OEMStatesEnum.OPERATIONAL
        self._location = oem_config["location"]
        self._distance_matrix = oem_config["distance_matrix"]
        self._total_shipping_cost = 0.0
        # Delays are given in days and converted to steps once, here.
        time_converter = world.time_converter()
        self._delivery_delay_steps = time_converter.days_to_steps(
            oem_config["delivery_delay"]
        )
        # Production spreads the units still needed over the delay. A delay under one
        # step means "make it all this step", so the divisor is at least 1.
        self._manufacture_delay_steps = max(
            1, time_converter.days_to_steps(oem_config["manufacture_delay"])
        )
        self._remanufacture_delay_steps = max(
            1, time_converter.days_to_steps(oem_config["remanufacture_delay"])
        )
        self._factory_stock = {
            ProductEnum.V: oem_config["virgin_stock"],
            ProductEnum.R: oem_config["reman_stock"],
        }
        self._production_rate = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._products_sold = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._sale_revenue = {ProductEnum.V: 0.0, ProductEnum.R: 0.0}
        self._total_products_produced = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._num_to_man = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._core_stock = oem_config["core_stock"]
        self._core_acceptance_rate = oem_config["core_acceptance_rate"]
        self._total_cores_collected = 0
        self._total_core_collection_cost = 0
        self._total_cores_rejected = 0
        self._total_cores_over_capacity = 0
        self._total_cores_not_collected = 0
        self._unit_production_cost_V = oem_config["unit_production_cost_V"]
        self._unit_production_cost_R = oem_config["unit_production_cost_R"]
        self._core_collection_cost = oem_config["core_collection_cost"]
        self._core_disposal_cost = oem_config["core_disposal_cost"]
        # Given in € per core per day; charged once per step
        self._core_storage_cost_per_step = time_converter.per_day_to_per_step(
            oem_config["core_storage_cost"]
        )
        self._total_core_storage_cost = 0.0
        self._core_storage_limit = oem_config["core_storage_limit"]
        self._total_acquisition_cost = 0.0
        self._retail_price_V = oem_config["retail_price_V"]
        self._retail_price_R = oem_config["retail_price_R"]
        self._inspection_cost = oem_config["inspection_cost"]
        self._total_inspection_costs = 0.0
        self._incoming_cores = []

        self._routing_enabled = oem_config.get("routing_heuristics", False)
        self._logistic_heuristics = {}
        if self._routing_enabled:
            self._logistic_heuristics = {
                k: oem_config[k]
                for k in (
                    "local_delivery_cost",
                    "shipping_cost_per_km",
                    "ferry_fee",
                    "driving_hours_per_day",
                )
            }

        self._reman_implementation_cost = oem_config["reman_implementation_cost"]
        # Given in € per year; charged once per step
        self._reman_operating_cost_per_step = time_converter.per_year_to_per_step(
            oem_config["reman_annual_operating_cost"]
        )
        self._total_reman_operating_cost = 0.0
        self._reman_enabled = ProductEnum.R in self._world.get_active_products()

        if self._reman_enabled:
            self._balance -= self._reman_implementation_cost
        # Core collection strategies only run alongside remanufacturing. Their
        # settings may still be in the config when reman is off: they are ignored.
        # .get keeps older scenario files (without the block) working.
        self._strategies = (
            build_strategies(
                oem_config.get("collection_strategies", {}),
                AgentEnum.OEM,
                time_converter,
            )
            if self._reman_enabled
            else []
        )
        self._total_contract_fees = 0.0

    def get_shipping_delay(self, destination: str) -> int:
        """
        Calculates the shipping delay based on routing data if available.
        1 day base + 1 day per 8 hours driving, +1 if ferry. Not sure of the validity or worth of this. Could be standard 2 days.
        """
        # Checks that there is a distance matrix and that the location being looked for is in that matrix
        # First check that intelligent logistics isnt disabled
        if not self._routing_enabled:
            return self._delivery_delay_steps
        if self._distance_matrix and self._location in self._distance_matrix:
            # Checks if you are sending it to the same place you are
            # The heuristics below work in days, so convert the result to steps
            time_converter = self._world.time_converter()
            if self._location == destination:
                return time_converter.days_to_steps(1)
            route = self._distance_matrix[self._location].get(destination)
            if route:
                hours = route["driving_hours"]
                days = 1 + int(
                    hours // self._logistic_heuristics["driving_hours_per_day"]
                )
                if route.get("has_ferry"):
                    days += 1
                return time_converter.days_to_steps(days)
        return self._delivery_delay_steps

    def get_shipping_cost(self, destination: str, default_cost: float) -> float:
        """
        Calculates shipping cost based on distance and route properties.
        Heuristic: €? per km + €? flat rate if ferry is involved. Again not sure if this is needed, really depends on the logistics method.
        """
        if not self._routing_enabled:
            return default_cost
        if self._distance_matrix and self._location in self._distance_matrix:
            if self._location == destination:
                return self._logistic_heuristics["local_delivery_cost"]
            route = self._distance_matrix[self._location].get(destination)
            # Really all made up, will get something more representative if needed or can remove and change to be static instead.
            if route:
                km = route["distance_km"]
                cost = km * self._logistic_heuristics["shipping_cost_per_km"]
                if route.get("has_ferry"):
                    cost += self._logistic_heuristics["ferry_fee"]
                return cost
        return default_cost

    def get_core_collection_cost(self, origin: str, default_cost: float) -> float:
        """
        Calculates core collection cost based on distance and route properties.
        Currently is the same logic as the shipping cost, but can be changed later.
        """
        return self.get_shipping_cost(origin, default_cost)

    def next(self, rng):
        """
        Execute the agent's actions for the current simulation tick.

        Args:
            rng (numpy.random.Generator): Random number generator.
        """
        self.process_incoming_cores(rng)
        self.update_manufacturing_counts()
        self.update_production()
        storage_cost = self._core_stock * self._core_storage_cost_per_step
        self._total_core_storage_cost += storage_cost
        self._balance -= storage_cost

        # Deduct the reman operating cost for this step (a share of the annual cost)
        if self._reman_enabled:
            self._balance -= self._reman_operating_cost_per_step
            self._total_reman_operating_cost += self._reman_operating_cost_per_step

    def get_tracking_metrics(self) -> dict:
        """
        Returns a dictionary of current OEM metrics for data collection.
        """
        return {
            "core_stock": self._core_stock,
            "virgin_stock": self._factory_stock[ProductEnum.V],
            "reman_stock": self._factory_stock[ProductEnum.R],
            "virgin_sold": self._products_sold[ProductEnum.V],
            "reman_sold": self._products_sold[ProductEnum.R],
            "cores_collected": self._total_cores_collected,
            "cores_rejected": self._total_cores_rejected,
            "inspection_cost": self._total_inspection_costs,
            "core_acquisition_cost": self._total_acquisition_cost,
            "lease_fees": self._total_contract_fees,
            "oem_balance": self._balance,
        }

    def record_core_not_collected(self) -> None:
        """Records a core that was not collected from a customer."""
        self._total_cores_not_collected += 1

    def contract_for(self, product: ProductEnum) -> Contract:
        """
        The terms a customer gets the product on. Owned by default; a strategy
        such as a lease can replace them.

        Args:
            product (ProductEnum): The product being acquired.

        Returns:
            Contract: The contract for this acquisition.
        """
        contract = Contract(kind=ContractKind.OWNED, operator=self, product=product)
        for strategy in self._strategies:
            contract = strategy.offer_contract(contract)
        return contract

    def core_return_probability(
        self, contract: Contract | None, base_probability: float
    ) -> float:
        """
        Probability that a customer's core comes back at end of life, after the
        active strategies have been applied to the customer's base return rate.

        Args:
            contract (Contract | None): The terms the product was held on.
            base_probability (float): The customer's own return rate.

        Returns:
            float: The return probability to use.
        """
        probability = base_probability
        for strategy in self._strategies:
            probability = strategy.return_probability(contract, probability)
        return probability

    def receive_contract_fee(self, amount: float) -> None:
        """
        Receive a per-step contract fee (e.g. a lease payment) from a customer.

        Args:
            amount (float): The fee for this step.
        """
        self._balance += amount
        self._total_contract_fees += amount

    # Checks the stock of a given product in storage
    def request_product(
        self, product: ProductEnum, customer_location: str | None = None
    ) -> Contract | None:
        """
        Process a customer's request to purchase a product.

        Args:
            product (ProductEnum): The type of product requested (Virgin or Reman).
            customer_location (str): The geographical location of the customer.

        Returns:
            Contract | None: The contract the customer gets the product on if it was
            in stock, None otherwise.
        """
        currentStock = self._factory_stock[product]

        if currentStock >= 1:
            self._factory_stock[product] -= 1
            self._products_sold[product] += 1
            # No longer charging the OEM for deliveries
            # if customer_location:
            #     shipping_cost = self.get_shipping_cost(customer_location, 20.0)
            #     self._total_shipping_cost += shipping_cost
            #     self._balance -= shipping_cost

            contract = self.contract_for(product)
            revenue = (
                self._retail_price_V
                if product == ProductEnum.V
                else self._retail_price_R
            )
            for strategy in self._strategies:
                revenue = strategy.sale_revenue(contract, revenue)
            self._balance += revenue
            self._sale_revenue[product] += revenue
            return contract

        return None

    def schedule_core_return(
        self, customer_location: str | None = None, contract: Contract | None = None
    ) -> None:
        """
        Schedules a core to be returned to the OEM after a shipping delay.

        Args:
            customer_location (str): The location of the customer returning the core.
            contract (Contract | None): The terms the product was held on.
        """
        delay = (
            self.get_shipping_delay(customer_location)
            if customer_location
            else self._delivery_delay_steps
        )  # Works depending on whether the customer location logic is used
        arrival_step = self._world.now() + delay
        self._incoming_cores.append(
            IncomingCore(arrival_step, customer_location, contract)
        )

    def process_incoming_cores(self, rng):
        """
        Process cores that have arrived after their return transit delay.
        """
        remaining_cores = []
        for core in self._incoming_cores:
            if self._world.now() >= core.arrival_step:
                self.return_product(rng, core.location, core.contract)
            else:
                remaining_cores.append(core)
        self._incoming_cores = remaining_cores

    def return_product(
        self,
        rng,
        customer_location: str | None = None,
        contract: Contract | None = None,
    ) -> None:
        """
        Process a returned product (core) from a customer.

        The core is either accepted into stock or rejected, based on the OEM's core acceptance rate.

        Args:
            rng (numpy.random.Generator): Seeded random number generator.
            customer_location (str): The geographical location of the customer.
            contract (Contract | None): The terms the product was held on.
        """
        self._total_cores_collected += 1

        if customer_location:
            collection_cost = self.get_core_collection_cost(
                customer_location, self._core_collection_cost
            )
        else:
            collection_cost = self._core_collection_cost
        for strategy in self._strategies:
            collection_cost = strategy.collection_cost(contract, collection_cost)

        self._total_core_collection_cost += collection_cost
        self._balance -= collection_cost

        # Add in inspection cost
        self._total_inspection_costs += self._inspection_cost
        self._balance -= self._inspection_cost

        acceptance_rate = self._core_acceptance_rate
        for strategy in self._strategies:
            acceptance_rate = strategy.acceptance_rate(contract, acceptance_rate)

        if rng.random() < acceptance_rate:
            # Pay the customer for the core if a strategy offers it (e.g. buy-back)
            payment = 0.0
            for strategy in self._strategies:
                payment = strategy.acquisition_cost(contract, payment)
            self._total_acquisition_cost += payment
            self._balance -= payment
            # Set a limit on how many cores to have in storage
            if self._core_stock < self._core_storage_limit:
                self._core_stock += 1
            else:
                # Saves the number of cores disposed of when the storage was full
                self._total_cores_over_capacity += 1
                self._balance -= self._core_disposal_cost
                pass
        else:
            self._total_cores_rejected += 1
            self._balance -= self._core_disposal_cost
            pass

    def leases_in_use(self) -> tuple[int, float]:
        """
        Count the products this OEM currently has out on lease, and the fees still
        due on them. Used for the end-of-run report: cash totals don't include fees
        that haven't been paid yet.

        Returns:
            tuple[int, float]: Units on lease, and remaining contracted fees (EUR).
        """
        units = 0
        remaining_fees = 0.0
        now = self._world.now()
        for agent in self._world.get_agents():
            if not isinstance(agent, Customer):
                continue
            contract = agent.contract()
            in_use = agent.end_of_life_step() >= 0
            if (
                contract is None
                or contract.operator is not self
                or contract.kind != ContractKind.LEASED
                or not in_use
            ):
                continue
            units += 1
            # One fee is paid per step up to and including the end-of-life step
            remaining_steps = max(0, agent.end_of_life_step() - now)
            remaining_fees += remaining_steps * contract.fee_per_step
        return units, remaining_fees

    def update_manufacturing_counts(self):
        """
        Count all the agents waiting for products and use that to update the manufacturing targets.
        """

        for agent in self._world.get_agents():
            if agent.type() == AgentEnum.CUSTOMER:
                if agent.state() == CustomerStatesEnum.WANTS_VIRGIN:
                    self._num_to_man[ProductEnum.V] += 1
                elif agent.state() == CustomerStatesEnum.WANTS_REMAN:
                    self._num_to_man[ProductEnum.R] += 1
                elif agent.state() == CustomerStatesEnum.WANTS_ANY:
                    # note that whilst this add two units to the queue to be made, it is deliberate
                    # this is just a way to resolve customers being stuck in the wants_any state for now
                    # also the production of reman or virgin units may be constrained by something else
                    # so even if they are due to be produced, they might not necissarily get produced
                    self._num_to_man[ProductEnum.V] += 1
                    self._num_to_man[ProductEnum.R] += 1

    def update_production(self):
        """
        Update production rates and inventory levels for both virgin and reman products.

        Virgin production is determined by current demand and manufacture delay.
        Remanufactured product production is limited by both current demand and available core stock.
        """

        for product in ProductEnum:
            # Only produce for demand not already covered by stock on the shelf
            still_needed = max(
                0.0, self._num_to_man[product] - self._factory_stock[product]
            )
            match product:
                case ProductEnum.V:
                    self._production_rate[product] = (
                        still_needed / self._manufacture_delay_steps
                    )
                    # if self._production_rate[product] > 3: # Could set a maximum production capacity
                    #     self._production_rate[product] = 3
                    self._factory_stock[product] += self._production_rate[product]
                    self._total_products_produced[product] += self._production_rate[
                        product
                    ]

                    self._balance -= (
                        self._production_rate[product] * self._unit_production_cost_V
                    )

                case ProductEnum.R:
                    if self._reman_enabled:
                        desired_production = (
                            still_needed / self._remanufacture_delay_steps
                        )
                        cores_per_unit = self._config["products"]["R"]["cores_consumed"]

                        # Production is limited by whichever runs out first: demand or cores
                        max_from_cores = self._core_stock / cores_per_unit
                        actual_production = min(desired_production, max_from_cores)

                        self._production_rate[product] = actual_production
                        self._factory_stock[product] += actual_production
                        self._total_products_produced[product] += actual_production
                        self._core_stock -= actual_production * cores_per_unit
                        self._balance -= (
                            actual_production * self._unit_production_cost_R
                        )
                    else:
                        self._production_rate[product] = 0

        for product in ProductEnum:
            self._num_to_man[product] = 0

    def generate_financial_report(self) -> dict:
        """
        Generate the financial report for the OEM.

        Returns:
            dict: A dictionary of Total Cost, Total Revenue, a more detailed cost breakdown, and some operational statistics.
        """

        # Production costs
        cost_V = (
            self._total_products_produced[ProductEnum.V] * self._unit_production_cost_V
        )
        cost_R = (
            self._total_products_produced[ProductEnum.R] * self._unit_production_cost_R
        )

        # Payments to customers for accepted cores (e.g. buy-back)
        cost_acquisition = self._total_acquisition_cost

        # Reverse logistics costs
        cost_collection = self._total_core_collection_cost

        # Disposal costs
        cost_disposal = (
            self._total_cores_rejected + self._total_cores_over_capacity
        ) * self._core_disposal_cost

        # Storage costs
        cost_storage = self._total_core_storage_cost

        # Outbound shipping cost
        # cost_outbound_shipping = self._total_shipping_cost

        # Inspection costs
        cost_inspection = self._total_inspection_costs

        cost_reman_impl = (
            self._reman_implementation_cost if self._reman_enabled else 0.0
        )
        cost_reman_op = self._total_reman_operating_cost if self._reman_enabled else 0.0

        cost_to_meet_demand = (
            cost_V
            + cost_R
            + cost_collection
            + cost_disposal
            + cost_storage
            + cost_acquisition
            + cost_inspection
            + cost_reman_impl
            + cost_reman_op
        )

        # Revenue as actually booked (a leased unit earns no sale price)
        revenue_V = self._sale_revenue[ProductEnum.V]
        revenue_R = self._sale_revenue[ProductEnum.R]
        revenue_lease = self._total_contract_fees

        revenue_total = revenue_V + revenue_R + revenue_lease

        units_on_lease, remaining_lease_fees = self.leases_in_use()

        return {
            "Total Cost": cost_to_meet_demand,
            "Total Revenue": revenue_total,
            "Breakdown": {
                "Production of virgin products": cost_V,
                "Production of reman products": cost_R,
                "Collecting cores": cost_collection,
                "Core acquisition payments": cost_acquisition,
                "Inspection of cores": cost_inspection,
                "Disposal of unaccepted cores": cost_disposal,
                "Storage of cores": cost_storage,
                "Sale of virgin products": revenue_V,
                "Sale of reman products": revenue_R,
                "Sale of lease contracts (fees)": revenue_lease,
                "Reman implementation cost": cost_reman_impl,
                "Reman operating cost": cost_reman_op,
            },
            "Statistics": {
                "Total units produced": self._total_products_produced[ProductEnum.V]
                + self._total_products_produced[ProductEnum.R],
                "Total units sold": self._products_sold[ProductEnum.V]
                + self._products_sold[ProductEnum.R],
                "Virgin units produced": self._total_products_produced[ProductEnum.V],
                "Virgin units sold": self._products_sold[ProductEnum.V],
                "Reman units produced": self._total_products_produced[ProductEnum.R],
                "Reman units sold": self._products_sold[ProductEnum.R],
                "Cores collected": self._total_cores_collected,
                "Cores not collected": self._total_cores_not_collected,
                "Cores accepted": (
                    self._total_cores_collected - self._total_cores_rejected
                ),
                "Cores rejected": self._total_cores_rejected,
                # Not in the totals above: fees still to come on leases running at the end
                "Units on lease at end": units_on_lease,
                "Remaining contracted lease fees": round(remaining_lease_fees, 2),
            },
        }
