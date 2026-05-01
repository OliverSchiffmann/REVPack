"""
Module for the Original Equipment Manufacturer (OEM) agent.
"""

from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING
from ._agent import AgentEnum, BaseAgent
from .message import Message, MessageType
from .product import ProductEnum, ProductDetails, product_params
from .customer import CustomerStatesEnum
from .states import OEMStatesEnum

if TYPE_CHECKING:
    from .world import World


class OEM(BaseAgent):
    """
    Original Equipment Manufacturer (OEM) agent.

    The OEM produces the virgin or reman product for the customers, processes the reman cores manages its own stock and production rates.
    """

    _state: OEMStatesEnum
    _balance: float
    _delivery_delay: int
    _manufacture_delay: int  # Sort of the time it takes to meet the demand (must be >=1 as you cant divide by 0)
    _remanufacture_delay: int
    _factory_stock: dict[ProductEnum, float]  # stock of products
    _production_rate: dict[ProductEnum, float]
    _products_sold: dict[ProductEnum, int]
    _total_products_produced: dict[ProductEnum, float]
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
    _core_storage_cost: float
    _total_core_storage_cost: float
    _core_storage_limit: int
    _bounties_returned: int
    _bounty_value: float
    _retail_price_V: float
    _retail_price_R: float
    _inspection_cost: float
    _total_inspection_costs: float
    _incoming_cores: list[tuple[int, str | None]]
    _config: dict
    _reman_implementation_cost: float
    _reman_annual_operating_cost: float
    _total_reman_operating_cost: float
    _reman_enabled: bool

    def __init__(self, id: int, world: World, config: dict) -> None:
        """
        Initialise the OEM agent.

        Args:
            id (int): Unique id for the agent.
            world (World): The simulation world the agent belongs to.
            config (dict): Configuration dictionary containing the OEM's parameters.

        Raises:
            ValueError: If manufacture_delay or remanufacture_delay is less than 1.
        """
        self._config = config
        oem_config = config["oem"]
        if oem_config["manufacture_delay"] < 1:
            raise ValueError(
                f"manufacture_delay must be >=1. Received: {oem_config['manufacture_delay']}"
            )
        if oem_config["remanufacture_delay"] < 1:
            raise ValueError(
                f"remanufacture_delay must be >=1. Received: {oem_config['remanufacture_delay']}"
            )
        super().__init__(id=id, type=AgentEnum.OEM, world=world)
        
        self._balance = config.get("balance", 0.0)
        
        self._state                      = OEMStatesEnum.OPERATIONAL
        self._location                   = oem_config.get("location", "Brescia")
        self._distance_matrix            = oem_config.get("distance_matrix", {})
        self._total_shipping_cost        = 0.0
        self._delivery_delay             = oem_config.get("delivery_delay", 1)
        self._manufacture_delay          = oem_config.get("manufacture_delay", 5)
        self._remanufacture_delay        = oem_config.get("remanufacture_delay", 5)
        self._factory_stock              = {
                                             ProductEnum.V: oem_config.get("virgin_stock", 0),
                                             ProductEnum.R: oem_config.get("reman_stock", 0),
                                         }
        self._production_rate            = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._products_sold              = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._total_products_produced    = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._num_to_man                 = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._core_stock                 = oem_config.get("core_stock", 0)
        self._core_acceptance_rate       = oem_config.get("core_acceptance_rate", 0.5)
        self._total_cores_collected      = 0
        self._total_core_collection_cost = 0
        self._total_cores_rejected       = 0
        self._total_cores_over_capacity  = 0
        self._total_cores_not_collected  = 0
        self._unit_production_cost_V     = oem_config.get("unit_production_cost_V", 500)
        self._unit_production_cost_R     = oem_config.get("unit_production_cost_R", 300)
        self._core_collection_cost       = oem_config.get("core_collection_cost", 15)
        self._core_disposal_cost         = oem_config.get("core_disposal_cost", 10)
        self._core_storage_cost          = oem_config.get("core_storage_cost", 0.0)
        self._total_core_storage_cost    = 0.0
        self._core_storage_limit         = oem_config.get("core_storage_limit", 100)
        self._bounties_returned          = 0
        self._bounty_value               = oem_config.get("bounty_value", 10.0)
        self._retail_price_V             = oem_config.get("retail_price_V", 1000)
        self._retail_price_R             = oem_config.get("retail_price_R", 1000)
        self._inspection_cost            = oem_config.get("inspection_cost", 0.0)
        self._total_inspection_costs     = 0.0
        self._incoming_cores             = []
        
        self._logistic_heuristics        = {
                                          "local_delivery_cost":oem_config.get("local_delivery_cost", 10.0),
                                          "shipping_cost_per_km":oem_config.get("shipping_cost_per_km", 0.01),
                                          "ferry_fee":oem_config.get("ferry_fee", 10.0),
                                          "driving_hours_per_day":oem_config.get("driving_hours_per_day", 8),
                                          }

        self._reman_implementation_cost  = oem_config["reman_implementation_cost"]
        self._reman_annual_operating_cost = oem_config["reman_annual_operating_cost"]
        self._total_reman_operating_cost = 0.0
        self._reman_enabled              = ProductEnum.R in self._world.get_active_products()

        if self._reman_enabled:
            self._balance -= self._reman_implementation_cost

    def get_shipping_delay(self, destination: str) -> int:
        """
        Calculates the shipping delay based on routing data if available.
        1 day base + 1 day per 8 hours driving, +1 if ferry. Not sure of the validity or worth of this. Could be standard 2 days.
        """
        # Checks that there is a distance matrix and that the location being looked for is in that matrix
        if self._distance_matrix and self._location in self._distance_matrix:
            # Checks if you are sending it to the same place you are
            if self._location == destination:
                return 1
            route = self._distance_matrix[self._location].get(destination)
            if route:
                hours = route["driving_hours"]
                days = 1 + int(hours // self._logistic_heuristics["driving_hours_per_day"])
                if route.get("has_ferry"):
                    days += 1
                return days
        return self._delivery_delay

    def get_shipping_cost(self, destination: str, default_cost: float) -> float:
        """
        Calculates shipping cost based on distance and route properties.
        Heuristic: €? per km + €? flat rate if ferry is involved. Again not sure if this is needed, really depends on the logistics method.
        """
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
        self._total_core_storage_cost += self._core_stock * self._core_storage_cost
        self._balance -= self._core_stock * self._core_storage_cost

        # Deduct reman annual operating cost proportionally per day
        if self._reman_enabled:
            daily_op_cost = self._reman_annual_operating_cost / 365.0
            self._balance -= daily_op_cost
            self._total_reman_operating_cost += daily_op_cost

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
            "bounty_values_paid": self._bounty_value * self._bounties_returned,
            "oem_balance": self._balance,
        }

    def record_core_not_collected(self) -> None:
        """Records a core that was not collected from a customer."""
        self._total_cores_not_collected += 1

    # Checks the stock of a given product in storage
    def request_product(
        self, product: ProductEnum, customer_location: str | None = None
    ) -> bool:
        """
        Process a customer's request to purchase a product.

        Args:
            product (ProductEnum): The type of product requested (Virgin or Reman).
            customer_location (str): The geographical location of the customer.

        Returns:
            bool: True if the product is in stock and successfully purchased, False otherwise.
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
                
            self._balance += self._retail_price_V if product == ProductEnum.V else self._retail_price_R
            return True

        return False

    def schedule_core_return(self, customer_location: str | None = None) -> None:
        """
        Schedules a core to be returned to the OEM after a shipping delay.

        Args:
            customer_location (str): The location of the customer returning the core.
        """
        delay = (
            self.get_shipping_delay(customer_location)
            if customer_location
            else self._delivery_delay
        )  # Works depending on whether the customer location logic is used
        arrival_day = self._world.now() + delay
        self._incoming_cores.append((arrival_day, customer_location))

    def process_incoming_cores(self, rng):
        """
        Process cores that have arrived after their return transit delay.
        """
        remaining_cores = []
        for arrival_day, location in self._incoming_cores:
            if self._world.now() >= arrival_day:
                self.return_product(rng, location)
            else:
                remaining_cores.append((arrival_day, location))
        self._incoming_cores = remaining_cores

    def return_product(self, rng, customer_location: str | None = None) -> None:
        """
        Process a returned product (core) from a customer.

        The core is either accepted into stock or rejected, based on the OEM's core acceptance rate.

        Args:
            rng (numpy.random.Generator): Seeded random number generator.
            customer_location (str): The geographical location of the customer.
        """
        self._total_cores_collected += 1

        # Pay the bounty
        self._bounties_returned += 1
        self._balance -= self._bounty_value

        if customer_location:
            collection_cost = self.get_core_collection_cost(
                customer_location, self._core_collection_cost
            )
        else:
            collection_cost = self._core_collection_cost

        self._total_core_collection_cost += collection_cost
        self._balance -= collection_cost

        # Add in inspection cost
        self._total_inspection_costs += self._inspection_cost
        self._balance -= self._inspection_cost

        if rng.random() < self._core_acceptance_rate:
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
                    self._num_to_man[ProductEnum.V] += 1
                    self._num_to_man[ProductEnum.R] += 1

    def update_production(self):
        """
        Update production rates and inventory levels for both virgin and reman products.

        Virgin production is determined by current demand and manufacture delay.
        Remanufactured product production is limited by both current demand and available core stock.
        """

        for product in ProductEnum:
            match product:
                case ProductEnum.V:
                    self._production_rate[product] = (
                        self._num_to_man[product] / self._manufacture_delay
                    )
                    # if self._production_rate[product] < 3: # Could set a maximum production capacity
                    #     self._production_rate[product] = 3
                    self._factory_stock[product] += self._production_rate[product]
                    self._total_products_produced[product] += self._production_rate[
                        product
                    ]

                    self._balance -= (
                        self._production_rate[product] * self._unit_production_cost_V
                    )

                case ProductEnum.R:
                    desired_production = (
                        self._num_to_man[product] / self._remanufacture_delay
                    )
                    cores_per_unit = (
                        self._config.get("products", {})
                        .get("R", {})
                        .get("cores_consumed", 1)
                    )

                    if desired_production * cores_per_unit > self._core_stock:
                        self._production_rate[product] = 0
                    else:
                        self._production_rate[product] = desired_production
                        self._factory_stock[product] += desired_production
                        self._total_products_produced[product] += desired_production
                        self._core_stock -= desired_production * cores_per_unit
                        self._balance -= (
                            desired_production * self._unit_production_cost_R
                        )

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

        # Return bounties paid
        cost_bounty = self._bounties_returned * self._bounty_value

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

        cost_reman_impl = self._reman_implementation_cost if self._reman_enabled else 0.0
        cost_reman_op = self._total_reman_operating_cost if self._reman_enabled else 0.0

        cost_to_meet_demand = (
            cost_V
            + cost_R
            + cost_collection
            + cost_disposal
            + cost_storage
            + cost_bounty
            + cost_inspection
            + cost_reman_impl
            + cost_reman_op
        )

        revenue_V = self._products_sold[ProductEnum.V] * self._retail_price_V

        revenue_R = self._products_sold[ProductEnum.R] * self._retail_price_R

        revenue_total = revenue_V + revenue_R

        return {
            "Total Cost": cost_to_meet_demand,
            "Total Revenue": revenue_total,
            "Breakdown": {
                "Production of virgin products": cost_V,
                "Production of reman products": cost_R,
                "Collecting cores": cost_collection,
                "Total bounties paid": cost_bounty,
                "Inspection of cores": cost_inspection,
                "Disposal of unaccepted cores": cost_disposal,
                "Storage of cores": cost_storage,
                "Sale of virgin products": revenue_V,
                "Sale of reman products": revenue_R,
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
                "Bounties returned": self._bounties_returned,
                "Cores collected": self._total_cores_collected,
                "Cores not collected": self._total_cores_not_collected,
                "Cores accepted": (
                    self._total_cores_collected - self._total_cores_rejected
                ),
                "Cores rejected": self._total_cores_rejected,
            },
        }
