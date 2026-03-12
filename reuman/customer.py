from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING
from ._agent import AgentEnum, BaseAgent
from .message import Message, MessageType
from .product import ProductEnum


patience: int = 10

if TYPE_CHECKING:
    from .world import World
    from .OEM import OEM


class CustomerStatesEnum(str, Enum):
    POTENTIAL_USER = "potential_user"
    WANTS_VIRGIN = "wants_virgin"
    USES_VIRGIN = "uses_virgin"
    WANTS_REMAN = "wants_reman"
    USES_REMAN = "uses_reman"
    WANTS_ANY = "wants_any"


product_params = {
    ProductEnum.V: {
        "lifespan": (
            17,
            24,
        ),  # number of days that a product might last for when in use
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
}  # need to add states here and in next()


class Customer(BaseAgent):
    _state: CustomerStatesEnum
    _delivery_day: int
    _end_of_life_day: int
    _active_product: ProductEnum | None
    _oem: OEM
    _patience: int
    _end_of_patience_day: int

    def __init__(self, id: int, world: World, oem: OEM, config: dict):
        self._state = CustomerStatesEnum.POTENTIAL_USER
        self._delivery_day = -1
        self._end_of_life_day = -1
        self._active_product = None
        super().__init__(id=id, type=AgentEnum.CUSTOMER, world=world)
        self._oem = oem
        self._patience = patience
        self._end_of_patience_day = -1

    def next(self, rng):
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
                        self._oem.return_proudct(rng)
                    else:
                        pass

    def try_and_buy(self, rng, product: ProductEnum):
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
        self._state = product_params[product]["uses_state"]
        self._active_product = product
        self._delivery_day = -1
        self._end_of_patience_day = -1

        lifespan_range = product_params[product]["lifespan"]
        lifespan = rng.integers(*lifespan_range)
        self._end_of_life_day = self._world.now() + lifespan
