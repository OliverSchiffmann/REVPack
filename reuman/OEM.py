from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING
from ._agent import AgentEnum, BaseAgent
from .message import Message, MessageType
from .product import ProductEnum


# Setup Parameters
virgin_stock: int = 10
core_stock: int = 0
reman_stock: int = 0  # inital stock of remanufactured units
delivery_delay: int = 1  # number of days for delivery between OEM and customer
remanufacture_delay = 3  # Sort of the time it takes for a core to be collected and turned into a reman product available to buy (must be >=1)
core_acceptance_rate: float = (
    0.7  # Captures the fact that not all cores are usable (cores from reman goods, different amounts of wear on product, etc)
)
unit_production_cost_V: float = 1000  # units are in EUR per single product unit
unit_production_cost_R: float = 200
core_collection_cost: float = 40  # Cost to collect a single core
core_disposal_cost: float = (
    20  # Cost to dispose of a single core if not accepted for reman
)
retail_price_V: float = 1200  # retail price of a virgin unit in EUR
retail_price_R: float = 900

if TYPE_CHECKING:
    from .world import World


class OEMStatesEnum(str, Enum):
    OPERATIONAL = "Operational"


class OEM(BaseAgent):
    _state: OEMStatesEnum
    _delivery_delay: int
    _manufacture_delay: int  # Sort of the time it takes to meet the demand (must be >=1 as you cant divide by 0)
    _remanufacture_delay: int
    _factory_stock: dict[ProductEnum, float]  # stock of products
    _production_rate: dict[ProductEnum, float]
    _products_sold: dict[ProductEnum, int]
    _total_products_produced: dict[ProductEnum, float]
    _core_stock: float  # inital stock of cores for remanufacturing
    _core_acceptance_rate: float
    _total_cores_collected: int
    _total_cores_rejected: int
    _unit_production_cost_V: float
    _unit_production_cost_R: float
    _core_collection_cost: float
    _core_disposal_cost: float
    _retail_price_V: float
    _retail_price_R: float

    def __init__(self, id: int, world: World, config: dict) -> None:
        if config["manufacture_delay"] < 1:
            raise ValueError(
                f"manufacture_delay must be >=1. Received: {config['manufacture_delay']}"
            )
        super().__init__(id=id, type=AgentEnum.OEM, world=world)
        self._state = OEMStatesEnum.OPERATIONAL
        self._delivery_delay = delivery_delay
        self._manufacture_delay = config["manufacture_delay"]
        self._remanufacture_delay = remanufacture_delay
        self._factory_stock = {
            ProductEnum.V: virgin_stock,
            ProductEnum.R: reman_stock,
        }
        self._production_rate = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._products_sold = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._total_products_produced = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._core_stock = core_stock
        self._core_acceptance_rate = core_acceptance_rate
        self._total_cores_collected = 0
        self._total_cores_rejected = 0
        self._unit_production_cost_V = unit_production_cost_V
        self._unit_production_cost_R = unit_production_cost_R
        self._core_collection_cost = core_collection_cost
        self._core_disposal_cost = core_disposal_cost
        self._retail_price_V = retail_price_V
        self._retail_price_R = retail_price_R

    def next(self, rng):
        self.update_production()

    def request_product(self, product: ProductEnum) -> bool:
        currentStock = self._factory_stock[product]

        if currentStock >= 1:
            self._factory_stock[product] -= 1
            self._products_sold[product] += 1
            return True

        return False

    def return_proudct(self, rng) -> None:
        self._total_cores_collected += 1
        if rng.random() < self._core_acceptance_rate:
            self._core_stock += 1
        else:
            self._total_cores_rejected += 1
            pass

    def update_production(self):
        for product in ProductEnum:
            match product:
                case ProductEnum.V:
                    self._production_rate[product] = (
                        self._world._num_wants[product] + self._world._num_wants_any
                    ) / self._manufacture_delay
                    self._factory_stock[product] += self._production_rate[product]
                    self._total_products_produced[product] += self._production_rate[
                        product
                    ]
                    # print(
                    #     f"Production Rate for {product.name}: {self._production_rate[product]:.4f}"
                    # )
                    # print(
                    #     f"Factory Stock of {product.name}: {self._factory_stock[product]:.4f}"
                    # )
                case ProductEnum.R:
                    desired_production = (
                        self._world._num_wants[product] + self._world._num_wants_any
                    ) / self._remanufacture_delay
                    maximum_production = self._core_stock / self._remanufacture_delay

                    self._production_rate[product] = min(
                        desired_production, maximum_production
                    )

                    self._factory_stock[product] += self._production_rate[product]
                    self._total_products_produced[product] += self._production_rate[
                        product
                    ]
                    self._core_stock -= self._production_rate[product]
                    # print(f"Core stock: {self._core_stock:.4f}")
                    # print(
                    #     f"Production Rate for {product.name}: {self._production_rate[product]:.4f}"
                    # )
                    # print(
                    #     f"Factory Stock of {product.name}: {self._factory_stock[product]:.4f}"
                    # )

    def generate_financial_report(self) -> dict:
        """Returns a dictionary containing cost breakdown and total."""

        # Production costs
        cost_V = (
            self._total_products_produced[ProductEnum.V] * self._unit_production_cost_V
        )
        cost_R = (
            self._total_products_produced[ProductEnum.R] * self._unit_production_cost_R
        )

        # Reverse logistics costs
        cost_collection = self._total_cores_collected * self._core_collection_cost

        # Disposal costs
        cost_disposal = self._total_cores_rejected * self._core_disposal_cost

        cost_to_meet_demand = cost_V + cost_R + cost_collection + cost_disposal

        revenue_V = self._products_sold[ProductEnum.V] * self._retail_price_V

        revenue_R = self._products_sold[ProductEnum.R] * self._retail_price_R

        revenue_total = revenue_V + revenue_R

        return {
            "Total Cost": cost_to_meet_demand,
            "Total Revenue": revenue_total,
            "Breakdown": {
                "Production of virgin products": cost_V,
                "Production of remanufactured products": cost_R,
                "Collecting cores": cost_collection,
                "Disposal of unaccepted cores": cost_disposal,
                "Sale of virgin products": revenue_V,
                "Sale of reman products": revenue_R,
            },
            "Statistics": {
                "Total units produced": self._total_products_produced[ProductEnum.V]
                + self._total_products_produced[ProductEnum.R],
                "Total units sold": self._products_sold[ProductEnum.V]
                + self._products_sold[ProductEnum.V],
                "Virgin units produced": self._total_products_produced[ProductEnum.V],
                "Virgin units sold": self._products_sold[ProductEnum.V],
                "Reman units produced": self._total_products_produced[ProductEnum.R],
                "Reman units sold": self._products_sold[ProductEnum.R],
                "Cores collected": self._total_cores_collected,
                "Cores accepted": (
                    self._total_cores_collected - self._total_cores_rejected
                ),
                "Cores rejected": self._total_cores_rejected,
            },
        }
