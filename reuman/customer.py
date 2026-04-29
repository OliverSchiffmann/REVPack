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
    WAITING_FOR_DELIVERY = "waiting_for_delivery"


class ProductDetails(TypedDict):
    """
    Typed dictionary defining simulation parameters for a given product type.

    Attributes:
        advertising_effectiveness (float): Probability of a potential user being influenced to buy.
        wants_state (CustomerStatesEnum): State to represent the desire for this product.
        uses_state (CustomerStatesEnum): State to represent active usage of this product.
        buy_message (MessageType): Message type sent when attempting to buy this product.
    """
    advertising_effectiveness: float
    wants_state: CustomerStatesEnum
    uses_state: CustomerStatesEnum
    buy_message: MessageType


product_params: dict[ProductEnum, ProductDetails] = {
    ProductEnum.V: {
        "advertising_effectiveness": 0.0006,
        "wants_state": CustomerStatesEnum.WANTS_VIRGIN,
        "uses_state": CustomerStatesEnum.USES_VIRGIN,
        "buy_message": MessageType.BUY_V,
    },
    ProductEnum.R: {
        "advertising_effectiveness": 0.0003,
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
    _product_lifespan: int
    _end_of_patience_day: int
    _core_return_rate: float
    _lifetime_method: str
    _mean_lifetime: int
    _lifetime_range: int

    def __init__(self, id: int, world: World, oem: OEM, config: dict, location: str = "Brescia"):
        """
        Initialise the Customer agent.

        Args:
            id (int): Unique identifier for the agent.
            world (World): The simulation world the agent belongs to.
            oem (OEM): The OEM agent to interact with.
            config (dict): Configuration dictionary with the customer parameters.
            location (str): Geographical location of the customer.
        """
        self._state = CustomerStatesEnum.POTENTIAL_USER
        self._location = location
        self._delivery_day = -1
        self._end_of_life_day = -1
        self._active_product = None
        super().__init__(id=id, type=AgentEnum.CUSTOMER, world=world)
        self._oem = oem
        self._patience = config["patience"]
        self._core_return_rate = config["core_return_rate"]
        self._end_of_patience_day = -1
        self._lifetime_method = config.get("lifetime_method", "triangular")
        self._mean_lifetime = config.get("mean_lifetime", 200)
        self._lifetime_range = config.get("lifetime_range", 3)

    def next(self, rng):
        """
        Execute the customer's actions for the current simulation tick.
        
        Behaviour changes based on the customer's current `CustomerStatesEnum`.

        Args:
            rng (numpy.random.Generator): Seeded random number generator.
        """
        match self._state:
            case CustomerStatesEnum.POTENTIAL_USER:
                self._handle_potential_user(rng)
            case state if state in [
                CustomerStatesEnum.WANTS_VIRGIN,
                CustomerStatesEnum.WANTS_REMAN,
                CustomerStatesEnum.WAITING_FOR_DELIVERY,
            ]:
                self._handle_waiting_customer(rng)
            case CustomerStatesEnum.WANTS_ANY:
                self._handle_wants_any(rng)
            case state if state in [
                CustomerStatesEnum.USES_VIRGIN,
                CustomerStatesEnum.USES_REMAN,
            ]:
                self._handle_active_user(rng)

    def _handle_potential_user(self, rng):
        """
        Handles logic for customers not yet in the market.
        """
        # this section is needed to avoid bias towards one product by always checking that first
        productsToConsider = self._world.get_active_products()
        rng.shuffle(productsToConsider)
        for product in productsToConsider:
            if (
                rng.random() < product_params[product]["advertising_effectiveness"]
            ):  # if a potential user is successfully influenced by ads
                self._state = product_params[product]["wants_state"]
                self._active_product = product
                self.try_and_buy(rng, product)
                break

    def _handle_waiting_customer(self, rng):
        """
        Handles logic for customers waiting for a specific product delivery or stock.
        """
        if self._delivery_day != -1:
            if self._world.now() >= self._delivery_day:
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

    def _handle_wants_any(self, rng):
        """
        Handles logic for customers who have lost patience and will take any available product.
        """
        productsToConsider = self._world.get_active_products()
        rng.shuffle(productsToConsider)
        for product in productsToConsider:
            self.try_and_buy(rng, product)
            if self._state != CustomerStatesEnum.WANTS_ANY:
                break


    def _handle_active_user(self, rng):
        """
        Handles logic for customers currently using a product until it reaches end-of-life. Going to add some logic so that customers lose interest at some point. 
        """
        if self._world.now() >= self._end_of_life_day:
                      
            if self._active_product is not None:
                self._state = product_params[self._active_product]["wants_state"]
                # Retain self._active_product so they attempt to buy the same product again
            
            self._delivery_day = -1           
            self._end_of_life_day = -1
            if ProductEnum.R in self._world.get_active_products():
                if rng.random() < self._core_return_rate:
                    self._oem.schedule_core_return(self._location)
                else:
                    self._oem._total_cores_not_collected += 1
            else:
                pass

    def try_and_buy(self, rng, product: ProductEnum):
        """
        Attempt to purchase a specified product from the OEM.

        Args:
            rng (numpy.random.Generator): Random number generator.
            product (ProductEnum): The type of product to attempt to buy.
        """
        purchaseSuccessful = self._oem.request_product(product, self._location)

        if purchaseSuccessful:
            delay = self._oem.get_shipping_delay(self._location)
            if delay == 0:  # checking if delivery is instant
                self.become_user(rng, product)
            else:
                self._state = CustomerStatesEnum.WAITING_FOR_DELIVERY
                self._active_product = product
                self._delivery_day = self._world.now() + delay
            self._end_of_patience_day = -1
        else:
            if self._end_of_patience_day == -1 and self._patience != -1: # was a bug where patience being -1 was the same as 0, -1 should be infinite patience
                self._end_of_patience_day = self._world.now() + self._patience

    def initialise_as_active_user(self, rng, product: ProductEnum):
        """
        Initialises the customer as an active user of the specified product with a random remaining lifespan.
        For creating some existing users.
        """
        self.become_user(rng, product)
        # Randomise the remaining lifespan to simulate users who bought the product at some point in the past
        if self._product_lifespan > 1:
            remaining_lifespan = int(rng.integers(1, self._product_lifespan + 1))
            self._end_of_life_day = self._world.now() + remaining_lifespan

    def become_user(self, rng, product: ProductEnum):
        """
        Changes the customer to a user of a specified product and sets the product lifespan depending on the config, if none give it uses a triangular distribution.

        Args:
            rng (numpy.random.Generator): Random number generator.
            product (ProductEnum): The product the customer is now using.
        """
        self._state = product_params[product]["uses_state"]
        self._active_product = product
        self._delivery_day = -1
        self._end_of_patience_day = -1
        
        # Determine the lifetime distribution method from config, defaults to triangular
        lifetime_method = self._lifetime_method
        
        if lifetime_method == "uniform":
            lifespan = self.get_uniform_lifetime(rng)
        elif lifetime_method == "weibull":
            lifespan = self.get_weibull_lifetime(rng)
        else:
            lifespan = self.get_triangular_lifetime(rng)

        self._product_lifespan = lifespan
        self._end_of_life_day = self._world.now() + lifespan
        
    def get_uniform_lifetime(self, rng):
        """
        Generates a uniform lifetime for the product based on the mean lifetime.

        Args:
            rng (numpy.random.Generator): Random number generator.

        Returns:
            int: The generated lifetime.
        """
        lifespan_mean = self._mean_lifetime
        lifespan_variation = self._lifetime_range
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
        lifespan_mean = self._mean_lifetime
        lifespan_variation = self._lifetime_range
        raw_lifespan = rng.triangular(lifespan_mean - lifespan_variation, lifespan_mean, lifespan_mean + lifespan_variation)
        return max(1, int(round(raw_lifespan))) # Rounded to the nearest integer 
    
    def get_weibull_lifetime(self, rng):
        """
        Generates a Weibull lifetime for the product based on the mean lifetime.
        
        Args:
            rng (numpy.random.Generator): Random number generator.

        Returns:
            int: The generated lifetime.
        """
        lifespan_mean = self._mean_lifetime
        
        # Set up the weibull parameters for the two halves (early failure and regular long life failure)
        defect_rate = 0.035   # 3.5% chance of early failure
        early_shape = 0.8     # Distribution shape (steep)
        early_scale = 0.5     # Dies very quickly
        normal_shape = 4.0    # Regular  shape
        
        # For a Weibull with a shape of 4.0, the Mean ≈ Scale * 0.906. Not sure the extent to which this is generalisable.
        normal_scale = lifespan_mean / 0.906 
        
        # Determine if its early failure or not.
        if rng.random() < defect_rate:
            # Draw from the early failure curve.
            raw_lifespan = rng.weibull(early_shape) * early_scale
        else:
            # If normal, draw from the wear-out curve.
            raw_lifespan = rng.weibull(normal_shape) * normal_scale
            
        return max(1, int(round(raw_lifespan))) # Rounded to the nearest integer
        

# Inherits everything from the normal customer class and does nothing different. You need 'pass' because you can't have an empty class, even if it inherits other stuff.
class B2B_Customer(Customer):
    """Business-to-Business (B2B) Customer agent. No difference from B2C for now."""
    pass

class B2C_Customer(Customer):
    """Business-to-Consumer (B2C) Customer agent."""
    pass