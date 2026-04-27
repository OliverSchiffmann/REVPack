"""
Module for the Original Equipment Manufacturer (OEM) agent.
"""

from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING
from ._agent import AgentEnum, BaseAgent
from .message import Message, MessageType
from .product import ProductEnum
from .customer import CustomerStatesEnum

if TYPE_CHECKING:
    from .world import World

class OEMStatesEnum(str, Enum):
    """Enum of possible states for the OEM agent."""
    OPERATIONAL = "Operational"


class OEM(BaseAgent):
    """
    Original Equipment Manufacturer (OEM) agent.

    The OEM produces the virgin or reman product for the customers, processes the reman cores manages its own stock and production rates.
    """

    _state: OEMStatesEnum
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
    _retail_price_V: float
    _retail_price_R: float

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
        if config["manufacture_delay"] < 1:
            raise ValueError(
                f"manufacture_delay must be >=1. Received: {config['manufacture_delay']}"
            )
        if config["remanufacture_delay"] < 1:
            raise ValueError(
                f"remanufacture_delay must be >=1. Received: {config['remanufacture_delay']}"
            )
        super().__init__(id=id, type=AgentEnum.OEM, world=world)
        self._state = OEMStatesEnum.OPERATIONAL
        self._location = config.get("location", "Brescia")
        self._distance_matrix = config.get("distance_matrix", {})
        self._total_shipping_cost = 0.0
        self._total_core_collection_cost_dynamic = 0.0
        self._delivery_delay = config["delivery_delay"]
        self._manufacture_delay = config["manufacture_delay"]
        self._remanufacture_delay = config["remanufacture_delay"]
        self._factory_stock = {
            ProductEnum.V: config["virgin_stock"],
            ProductEnum.R: config["reman_stock"],
        }
        self._production_rate = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._products_sold = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._total_products_produced = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._num_to_man = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._core_stock = config["core_stock"]
        self._core_acceptance_rate = config["core_acceptance_rate"]
        self._total_cores_collected = 0
        self._total_cores_rejected = 0
        self._total_cores_over_capacity = 0
        self._total_cores_not_collected = 0
        self._unit_production_cost_V = config["unit_production_cost_V"]
        self._unit_production_cost_R = config["unit_production_cost_R"]
        self._core_collection_cost = config["core_collection_cost"]
        self._core_disposal_cost = config["core_disposal_cost"]
        self._core_storage_cost = config.get("core_storage_cost", 0.0)
        self._total_core_storage_cost = 0.0
        self._retail_price_V = config["retail_price_V"]
        self._retail_price_R = config["retail_price_R"]

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
                days = 1 + int(hours // 8)
                if route.get("has_ferry"):
                    days += 1
                return days
        return self._delivery_delay

    def get_shipping_cost(self, destination: str, default_cost: float) -> float:
        """
        Calculates shipping cost based on distance and route properties.
        Heuristic: €0.5 per km + €50 flat rate if ferry is involved. Again not sure if this is needed, really depends on the logistics method.
        """
        if self._distance_matrix and self._location in self._distance_matrix:
            if self._location == destination:
                return 10.0 # Standard local delivery cost
            route = self._distance_matrix[self._location].get(destination)
            # Really all made up, will get something more representative if needed or can remove and change to be static instead.
            if route:
                km = route["distance_km"]
                cost = km * 0.01
                if route.get("has_ferry"):
                    cost += 10.0
                return cost
        return default_cost

    def next(self, rng):
        """
        Execute the agent's actions for the current simulation tick.

        Args:
            rng (numpy.random.Generator): Random number generator.
        """
        self.update_manufacturing_counts()
        self.update_production()
        self._total_core_storage_cost += self._core_stock * self._core_storage_cost

    # Checks the stock of a given product in storage
    def request_product(self, product: ProductEnum, customer_location: str | None = None) -> bool:
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
            if customer_location:
                self._total_shipping_cost += self.get_shipping_cost(customer_location, 20.0)
            return True

        return False

    def return_product(self, rng, customer_location: str | None = None) -> None:
        """
        Process a returned product (core) from a customer.

        The core is either accepted into stock or rejected, based on the OEM's core acceptance rate.

        Args:
            rng (numpy.random.Generator): Seeded random number generator.
            customer_location (str): The geographical location of the customer.
        """
        self._total_cores_collected += 1
        if customer_location:
            self._total_core_collection_cost_dynamic += self.get_shipping_cost(customer_location, self._core_collection_cost)
        else:
            self._total_core_collection_cost_dynamic += self._core_collection_cost

        if rng.random() < self._core_acceptance_rate:
            # Set a limit on how many cores to have in storage
            if self._core_stock < 100:
                self._core_stock += 1
            else:
                # Saves the number of cores disposed of when the storage was full
                self._total_cores_over_capacity += 1
        else:
            self._total_cores_rejected += 1
            pass

    def update_manufacturing_counts(self):
        """
        Count all the agents waiting for products and use that to update the manufacturing targets.
        """
        
        for agent in self._world._agents.values():
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
                    self._production_rate[product] = self._num_to_man[product] / self._manufacture_delay
                    # if self._production_rate[product] < 3: # Could set a maximum production capacity
                    #     self._production_rate[product] = 3                        
                    self._factory_stock[product] += self._production_rate[product]
                    self._total_products_produced[product] += self._production_rate[product]
                
                case ProductEnum.R:
                    desired_production = self ._num_to_man[product] / self._remanufacture_delay
                    maximum_production = self._core_stock / self._remanufacture_delay # Could set a maximum production capacity on top of the core limitation

                    self._production_rate[product] = min(
                        desired_production, maximum_production
                    )

                    self._factory_stock[product] += self._production_rate[product]
                    self._total_products_produced[product] += self._production_rate[product]
                    self._core_stock -= self._production_rate[product]

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

        # Reverse logistics costs
        if self._total_core_collection_cost_dynamic > 0:
            cost_collection = self._total_core_collection_cost_dynamic
        else:
            cost_collection = self._total_cores_collected * self._core_collection_cost

        # Disposal costs
        cost_disposal = (self._total_cores_rejected + self._total_cores_over_capacity) * self._core_disposal_cost

        # Storage costs
        cost_storage = self._total_core_storage_cost

        # Outbound shipping cost
        cost_outbound_shipping = self._total_shipping_cost

        cost_to_meet_demand = cost_V + cost_R + cost_collection + cost_disposal + cost_storage + cost_outbound_shipping

        revenue_V = self._products_sold[ProductEnum.V] * self._retail_price_V

        revenue_R = self._products_sold[ProductEnum.R] * self._retail_price_R

        revenue_total = revenue_V + revenue_R

        return {
            "Total Cost": cost_to_meet_demand,
            "Total Revenue": revenue_total,
            "Breakdown": {
                "Production of virgin products": cost_V,
                "Production of remanufactured products": cost_R,
                "Outbound shipping": cost_outbound_shipping,
                "Collecting cores": cost_collection,
                "Disposal of unaccepted cores": cost_disposal,
                "Storage of cores": cost_storage,
                "Sale of virgin products": revenue_V,
                "Sale of reman products": revenue_R,
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
            },
        }
