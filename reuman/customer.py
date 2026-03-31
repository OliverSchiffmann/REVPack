"""
Module for the Customer agents.
"""

from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING, TypedDict
from ._agent import AgentEnum, BaseAgent
from .message import Message, MessageType
from .product import ProductEnum

if TYPE_CHECKING:
    from .world import World
    from .OEM import OEM


class CustomerStatesEnum(str, Enum):
    """Enum of possible states for a Customer agent."""
    POTENTIAL_USER = "potential_user"
    WANTS_VIRGIN = "wants_virgin"
    USES_VIRGIN = "uses_virgin"
    WANTS_REMAN = "wants_reman"
    USES_REMAN = "uses_reman"
    WANTS_ANY = "wants_any"


class ProductDetails(TypedDict):
    """
    Typed dictionary defining simulation parameters for a given product type.

    Attributes:
        lifespan (tuple[int, int]): The range of days a product might last when in use.
        advertising_effectiveness (float): Probability of a potential user being influenced to buy.
        wom_threshold (float): Threshold for word-of-mouth influence.
        wants_state (CustomerStatesEnum): State to represent the desire for this product.
        uses_state (CustomerStatesEnum): State to represent active usage of this product.
        buy_message (MessageType): Message type sent when attempting to buy this product.
    """
    lifespan: tuple[int, int]
    advertising_effectiveness: float
    wom_threshold: float
    wants_state: CustomerStatesEnum
    uses_state: CustomerStatesEnum
    buy_message: MessageType


product_params: dict[ProductEnum, ProductDetails] = {
    ProductEnum.V: {
        "lifespan": (17, 24),  # number of days that a product might last for when in use
        "advertising_effectiveness": 0.011,
        "wom_threshold": 0.015,
        "wants_state": CustomerStatesEnum.WANTS_VIRGIN,
        "uses_state": CustomerStatesEnum.USES_VIRGIN,
        "buy_message": MessageType.BUY_V,
    },
    ProductEnum.R: {
        "lifespan": (17, 24),
        "advertising_effectiveness": 0.011,
        "wom_threshold": 0.015,
        "wants_state": CustomerStatesEnum.WANTS_REMAN,
        "uses_state": CustomerStatesEnum.USES_REMAN,
        "buy_message": MessageType.BUY_R,
    },
}


class Customer(BaseAgent):
    """
    Base Customer agent representing either an individual or a business in the market.

    Customers transition through various states (potential user, wanting a product, 
    using a product) based on advertising, OEM stock availability, delivery delays, 
    customer patience, and product lifespans. A visualisation is shown in [[provide the state chart?]].
    """
    _state: CustomerStatesEnum
    _delivery_day: int
    _end_of_life_day: int
    _active_product: ProductEnum | None
    _oem: OEM
    _patience: int
    _end_of_patience_day: int
    _config: dict

    def __init__(self, id: int, world: World, oem: OEM, config: dict):
        """
        Initialise the Customer agent.

        Args:
            id (int): Unique identifier for the agent.
            world (World): The simulation world the agent belongs to.
            oem (OEM): The OEM agent to interact with.
            config (dict): Configuration dictionary with the customer parameters.
        """
        self._state = CustomerStatesEnum.POTENTIAL_USER
        self._config = config
        self._delivery_day = -1
        self._end_of_life_day = -1
        self._active_product = None
        super().__init__(id=id, type=AgentEnum.CUSTOMER, world=world)
        self._oem = oem
        self._patience = self._config["patience"]
        self._end_of_patience_day = -1

    def next(self, rng):
        """
        Execute the customer's actions for the current simulation tick.
        
        Behaviour changes based on the customer's current `CustomerStatesEnum`.

        Args:
            rng (numpy.random.Generator): Seeded random number generator.
        """
        match self._state:
            case CustomerStatesEnum.POTENTIAL_USER:
                # this section is needed to avoid bias towards one product by always checking that first
                productsToConsider = self._world.get_active_products()
                rng.shuffle(productsToConsider)
                for product in productsToConsider:
                    if (
                        rng.random()
                        < product_params[product]["advertising_effectiveness"]
                    ):  # if a potential user is successfully influenced by ads
                        self.try_and_buy(rng, product)
                        break
            case state if state in [
                CustomerStatesEnum.WANTS_VIRGIN,
                CustomerStatesEnum.WANTS_REMAN,
            ]:
                if self._delivery_day != -1:
                    if self._world.now() == self._delivery_day:
                        if self._active_product:
                            self.become_user(rng, self._active_product)
                elif (
                    self._end_of_patience_day != -1
                    and self._world.now() >= self._end_of_patience_day
                ):
                    # Patience ran out
                    self._state = CustomerStatesEnum.WANTS_ANY
                else:
                    if self._active_product is not None:
                        self.try_and_buy(rng, self._active_product)

            case CustomerStatesEnum.WANTS_ANY:
                productsToConsider = self._world.get_active_products()
                rng.shuffle(productsToConsider)
                for product in productsToConsider:
                    if self._oem.request_product(product):
                        # Found something to buy
                        if self._oem._delivery_delay == 0:
                            self.become_user(rng, product)
                        else:
                            self._state = product_params[product]["wants_state"]
                            self._active_product = product
                            self._delivery_day = (
                                self._world.now() + self._oem._delivery_delay
                            )
                            self._end_of_patience_day = -1
                        return

            case state if state in [
                CustomerStatesEnum.USES_VIRGIN,
                CustomerStatesEnum.USES_REMAN,
            ]:
                if self._world.now() == self._end_of_life_day:
                    product_to_rebuy = self._active_product

                    if (
                        product_to_rebuy is None
                    ):  # This seems superfluous but its so python/IDE knows that product to rebuy wont be None
                        if state == CustomerStatesEnum.USES_REMAN:
                            product_to_rebuy = ProductEnum.R
                        else:
                            product_to_rebuy = ProductEnum.V

                    self._state = product_params[product_to_rebuy]["wants_state"]
                    self._end_of_life_day = -1
                    if ProductEnum.R in self._world.get_active_products():
                        self._oem.return_product(rng)
                    else:
                        pass

    def try_and_buy(self, rng, product: ProductEnum):
        """
        Attempt to purchase a specified product from the OEM.

        Args:
            rng (numpy.random.Generator): Random number generator.
            product (ProductEnum): The type of product to attempt to buy.
        """
        purchaseSuccessful = self._oem.request_product(product)

        if purchaseSuccessful:
            if self._oem._delivery_delay == 0:  # checking if delivery is instant
                self.become_user(rng, product)
            else:
                self._state = product_params[product]["wants_state"]
                self._active_product = product
                self._delivery_day = self._world.now() + self._oem._delivery_delay
            self._end_of_patience_day = -1
        else:
            self._state = product_params[product]["wants_state"]
            self._active_product = product
            if self._end_of_patience_day == -1:
                self._end_of_patience_day = self._world.now() + self._patience

    def become_user(self, rng, product: ProductEnum):
        """
        Changes the customer to a user of a specified product and sets the product lifespan.

        Args:
            rng (numpy.random.Generator): Random number generator.
            product (ProductEnum): The product the customer is now using.
        """
        self._state = product_params[product]["uses_state"]
        self._active_product = product
        self._delivery_day = -1
        self._end_of_patience_day = -1
        
        # lifespan_range = product_params[product]["lifespan"]
        lifespan_mean = self._config["mean_lifetime"]
        lifespan_range = (lifespan_mean - 3, lifespan_mean + 3)
        lifespan = rng.integers(*lifespan_range)
        self._end_of_life_day = self._world.now() + lifespan
        
    def get_uniform_lifetime(self, rng):
        """
        Generates a uniform lifetime for the product based on the mean lifetime.

        Args:
            rng (numpy.random.Generator): Random number generator.

        Returns:
            int: The generated lifetime.
        """
        lifespan_mean = self._config["mean_lifetime"]
        lifespan_variation = self._config.get("lifetime_range", 3)
        lifespan_range = (lifespan_mean - lifespan_variation, lifespan_mean + lifespan_variation)
        return rng.integers(*lifespan_range)
    
    def get_triangular_lifetime(self, rng):
        """
        Generates a triangular lifetime for the product based on the mean lifetime.
        
        Args:
            rng (numpy.random.Generator): Random number generator.

        Returns:
            int: The generated lifetime.
        """
        lifespan_mean = self._config["mean_lifetime"]
        lifespan_variation = self._config.get("lifetime_range", 3)
        return rng.triangular(lifespan_mean - lifespan_variation, lifespan_mean, lifespan_mean + lifespan_variation)
    
    def get_weibull_lifetime(self, rng):
        """
        Generates a Weibull lifetime for the product based on the mean lifetime.
        
        Args:
            rng (numpy.random.Generator): Random number generator.

        Returns:
            int: The generated lifetime.
        """
        lifespan_mean = self._config["mean_lifetime"]
        
        # --- Mixture Model Parameters ---
        # (Tip: You might want to move these constants into self._config later)
        defect_rate = 0.035   # 3.5% chance of early failure
        early_shape = 0.8     # Infant mortality shape (< 1)
        early_scale = 0.5     # Dies very quickly
        normal_shape = 4.0    # Standard wear-out shape for hardware
        
        # Dynamically calculate the scale for the normal units so it hits your config's target mean.
        # For a Weibull with a shape of 4.0, the Mean ≈ Scale * 0.906
        normal_scale = lifespan_mean / 0.906 
        
        # 1. Determine which batch this specific agent belongs to
        if rng.random() < defect_rate:
            # It's a defective unit! Draw from the early failure curve.
            raw_lifespan = rng.weibull(early_shape) * early_scale
        else:
            # It's a normal unit! Draw from the wear-out curve.
            raw_lifespan = rng.weibull(normal_shape) * normal_scale
            
        return raw_lifespan
        

# Inherits everything from the normal customer class and does nothing different. You need 'pass' because you can't have an empty class, even if it inherits other stuff.
class B2B_Customer(Customer):
    """Business-to-Business (B2B) Customer agent. No difference from B2C for now."""
    pass

class B2C_Customer(Customer):
    """Business-to-Consumer (B2C) Customer agent."""
    pass