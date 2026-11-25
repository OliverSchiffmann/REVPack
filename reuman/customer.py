"""
Module for the Customer agents.
"""

from __future__ import annotations
import math
from typing import TYPE_CHECKING
from ._agent import AgentEnum, BaseAgent
from .states import CustomerStatesEnum
from .product import ProductEnum, ProductDetails, product_params
from .collection_strategies import Contract, ContractKind

if TYPE_CHECKING:
    from .world import World
    from .OEM import OEM


class Customer(BaseAgent):
    """
    Base Customer agent representing either an individual or a business in the market.

    Customers transition through various states (potential user, wanting a product,
    using a product) based on advertising, OEM stock availability, delivery delays,
    customer patience, and product lifespans.
    """

    _state: CustomerStatesEnum
    _delivery_step: int
    _end_of_life_step: int
    _active_product: ProductEnum | None
    _contract: Contract | None  # terms of the product being waited for or used
    _oem: OEM
    _patience_steps: int  # -1 means infinite patience
    _product_lifespan: int
    _end_of_patience_step: int
    _core_return_rate: float
    _config: dict
    _lifetime_method: str
    _mean_lifetime_days: float
    _lifetime_range_days: float
    _customer_config: dict

    def __init__(
        self,
        id: int,
        world: World,
        oem: OEM,
        config: dict,
        customer_type: str = "b2b_customer",
        location: str = "Brescia",
    ):
        """
        Initialise the Customer agent.

        Args:
            id (int): Unique identifier for the agent.
            world (World): The simulation world the agent belongs to.
            oem (OEM): The OEM agent to interact with.
            config (dict): Full configuration dictionary for the simulation.
            customer_type (str): Key to access the correct customer sub-config ("b2b_customer" or "b2c_customer").
            location (str): Geographical location of the customer.
        """
        self._state = CustomerStatesEnum.POTENTIAL_USER
        self._config = config  # full config - for shared params e.g. products
        self._customer_config = config[
            customer_type
        ]  # customer-specific params e.g. patience, lifetime. We know this is cursed
        self._location = location
        self._delivery_step = -1
        self._end_of_life_step = -1
        self._active_product = None
        self._contract = None
        super().__init__(id=id, type=AgentEnum.CUSTOMER, world=world)
        self._oem = oem
        # Patience is given in days. -1 means "never gives up" and is kept as-is.
        # At least 1 step, so a customer always gets the in-step retry after the
        # OEM has produced, before giving up (0 would skip it).
        patience_days = self._customer_config["patience"]
        if patience_days == -1:
            self._patience_steps = -1
        else:
            self._patience_steps = max(
                1, world.time_converter().days_to_steps(patience_days)
            )
        self._core_return_rate = self._customer_config["core_return_rate"]
        self._end_of_patience_step = -1
        self._lifetime_method = self._customer_config["lifetime_method"]
        self._mean_lifetime_days = self._customer_config["mean_lifetime"]
        self._lifetime_range_days = self._customer_config["lifetime_range"]
        # Only used by the "weibull" method. .get keeps older scenario files working.
        self._lifetime_shape = self._customer_config.get("lifetime_shape", 4.0)
        self._early_failure_share = self._customer_config.get(
            "early_failure_share", 0.035
        )
        if self._lifetime_shape <= 0:
            raise ValueError(
                f"lifetime_shape must be > 0. Received: {self._lifetime_shape}"
            )
        if not 0 <= self._early_failure_share <= 1:
            raise ValueError(
                "early_failure_share must be between 0 and 1. "
                f"Received: {self._early_failure_share}"
            )

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
        # Agents no longer independently decide to enter the market.
        # This is now handled centrally by World.generate_demand()
        pass

    def force_market_entry(self, rng, product: ProductEnum):
        """Called centrally by the World to transition agent out of POTENTIAL_USER state."""
        if self._oem.supplies_from_stock():
            # The customer takes whatever the OEM has in stock, so the product
            # the demand profile picked doesn't matter
            self._state = CustomerStatesEnum.WANTS_ANY
            self._active_product = None
            self.try_and_buy(rng, None)
            return
        self._state = product_params[product]["wants_state"]
        self._active_product = product
        self.try_and_buy(rng, product)

    def _handle_waiting_customer(self, rng):
        """
        Handles logic for customers waiting for a specific product delivery or stock.
        """
        if self._delivery_step != -1:
            if self._world.now() >= self._delivery_step:
                if self._active_product:
                    self.become_user(rng, self._active_product)
        elif (
            self._end_of_patience_step != -1
            and self._world.now() >= self._end_of_patience_step
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
        if self._oem.supplies_from_stock():
            self.try_and_buy(rng, None)  # the OEM picks from its stock
            return
        productsToConsider = self._world.get_active_products()
        rng.shuffle(productsToConsider)
        for product in productsToConsider:
            self.try_and_buy(rng, product)
            if self._state != CustomerStatesEnum.WANTS_ANY:
                break

    def _handle_active_user(self, rng):
        """
        Handles logic for customers currently using a product until it reaches end-of-life.
        """
        contract = self._contract
        # Pay any per-step fee (e.g. a lease) for every step the product is used
        if contract is not None and contract.fee_per_step > 0:
            contract.operator.receive_contract_fee(contract.fee_per_step)
        if self._world.now() >= self._end_of_life_step:

            if self._active_product is not None:
                self._state = CustomerStatesEnum.WANTS_ANY
                self._active_product = None

            self._delivery_step = -1
            self._end_of_life_step = -1
            self._contract = None
            if ProductEnum.R in self._world.get_active_products():
                # The core goes back to whoever the contract was with
                collector = contract.operator if contract is not None else self._oem
                return_probability = collector.core_return_probability(
                    contract, self._core_return_rate
                )
                if rng.random() < return_probability:
                    collector.schedule_core_return(self._location, contract)
                else:
                    collector.record_core_not_collected()

    def contract(self) -> Contract | None:
        """The terms of the product being waited for or used (None if neither)."""
        return self._contract

    def end_of_life_step(self) -> int:
        """Step at which the product in use reaches end of life (-1 if not in use)."""
        return self._end_of_life_step

    def try_and_buy(self, rng, product: ProductEnum | None):
        """
        Attempt to purchase a specified product from the OEM.

        Args:
            rng (numpy.random.Generator): Random number generator.
            product (ProductEnum | None): The type of product to attempt to buy,
                or None to take whatever the OEM has in stock.
        """
        contract = self._oem.request_product(product, self._location)

        if contract is not None:
            self._contract = contract
            product = contract.product  # the product actually received
            delay = self._oem.get_shipping_delay(self._location)
            if delay == 0:  # checking if delivery is instant
                self.become_user(rng, product)
            else:
                self._state = CustomerStatesEnum.WAITING_FOR_DELIVERY
                self._active_product = product
                self._delivery_step = self._world.now() + delay
            self._end_of_patience_step = -1
        else:
            if (
                self._end_of_patience_step == -1 and self._patience_steps != -1
            ):  # patience of -1 means infinite patience
                self._end_of_patience_step = self._world.now() + self._patience_steps

    def initialise_as_active_user(self, rng, product: ProductEnum):
        """
        Initialises the customer as an active user of the specified product with a random remaining lifespan.
        For creating some existing users at the start of the simulation.

        These units were bought before the simulation (and before any collection
        strategy), so they are always owned, even when a lease is on: their owners
        lease only when they replace them.
        """
        self._contract = Contract(
            kind=ContractKind.OWNED, operator=self._oem, product=product
        )
        self.become_user(rng, product)
        # Randomise the remaining lifespan to simulate users who bought the product at some point in the past
        if self._product_lifespan > 1:
            remaining_lifespan = int(rng.integers(1, self._product_lifespan + 1))
            self._end_of_life_step = self._world.now() + remaining_lifespan

    def become_user(self, rng, product: ProductEnum):
        """
        Changes the customer to a user of a specified product and sets the product lifespan
        from customer config, using a triangular distribution by default.

        Args:
            rng (numpy.random.Generator): Random number generator.
            product (ProductEnum): The product the customer is now using.
        """
        self._state = product_params[product]["uses_state"]
        self._active_product = product
        self._delivery_step = -1
        self._end_of_patience_step = -1
        # Users who never went through try_and_buy (e.g. starting customers) still need terms
        if self._contract is None:
            self._contract = self._oem.contract_for(product)

        if self._contract.term_steps is not None:
            # A fixed-term contract (e.g. a lease) sets the end of life, not the drawn lifetime
            lifespan_steps = self._contract.term_steps
        else:
            if self._lifetime_method == "uniform":
                lifespan = self.get_uniform_lifetime(rng)
            elif self._lifetime_method == "weibull":
                lifespan = self.get_weibull_lifetime(rng)
            elif self._lifetime_method == "triangular":
                lifespan = self.get_triangular_lifetime(rng)
            else:
                raise ValueError(f"Unknown lifetime method: {self._lifetime_method}")

            # Lifetimes are drawn in days, then converted. At least 1 step: a product
            # that is bought is always used for some time before it reaches end of life.
            lifespan_steps = max(
                1, self._world.time_converter().days_to_steps(lifespan)
            )
        self._product_lifespan = lifespan_steps
        self._end_of_life_step = self._world.now() + lifespan_steps

    def get_uniform_lifetime(self, rng):
        """
        Generates a uniform lifetime for the product based on the mean lifetime.

        Args:
            rng (numpy.random.Generator): Random number generator.

        Returns:
            int: The generated lifetime.
        """
        lifespan_mean = self._mean_lifetime_days
        lifespan_variation = self._lifetime_range_days
        lifespan_range = (
            lifespan_mean - lifespan_variation,
            lifespan_mean + lifespan_variation,
        )
        return rng.integers(*lifespan_range)

    def get_triangular_lifetime(self, rng):
        """
        Generates a triangular lifetime for the product based on the mean lifetime.

        Args:
            rng (numpy.random.Generator): Random number generator.

        Returns:
            int: The generated lifetime.
        """
        lifespan_mean = self._mean_lifetime_days
        lifespan_variation = self._lifetime_range_days
        raw_lifespan = rng.triangular(
            lifespan_mean - lifespan_variation,
            lifespan_mean,
            lifespan_mean + lifespan_variation,
        )
        return max(1, int(round(raw_lifespan)))  # Rounded to the nearest integer

    def get_weibull_lifetime(self, rng):
        """
        Generates a Weibull lifetime for the product based on the mean lifetime.

        Args:
            rng (numpy.random.Generator): Random number generator.

        Returns:
            int: The generated lifetime.
        """
        lifespan_mean = self._mean_lifetime_days

        # Set up the Weibull parameters for the two halves (early failure and wear-out)
        defect_rate = self._early_failure_share  # chance of early failure
        early_shape = 0.8  # Distribution shape (steep)
        early_scale = 0.5  # Dies very quickly
        normal_shape = self._lifetime_shape  # wear-out shape

        # The mean of a Weibull is scale * Gamma(1 + 1/shape), so this scale gives
        # the requested mean (Gamma(1.25) = 0.906 for the old fixed shape of 4)
        normal_scale = lifespan_mean / math.gamma(1 + 1 / normal_shape)

        if rng.random() < defect_rate:
            raw_lifespan = rng.weibull(early_shape) * early_scale
        else:
            raw_lifespan = rng.weibull(normal_shape) * normal_scale

        return max(1, int(round(raw_lifespan)))  # Rounded to the nearest integer


# Inherits everything from the base Customer class.
class B2B_Customer(Customer):
    """Business-to-Business (B2B) Customer agent. No difference from B2C for now."""

    def __init__(self, id, world, oem, config, location="Brescia"):
        super().__init__(
            id=id,
            world=world,
            oem=oem,
            config=config,
            customer_type="b2b_customer",
            location=location,
        )


class B2C_Customer(Customer):
    """Business-to-Consumer (B2C) Customer agent."""

    def __init__(self, id, world, oem, config, location="Brescia"):
        super().__init__(
            id=id,
            world=world,
            oem=oem,
            config=config,
            customer_type="b2c_customer",
            location=location,
        )
