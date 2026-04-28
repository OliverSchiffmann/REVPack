from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING, TypedDict
from .message import MessageType
from .states import CustomerStatesEnum  # no TYPE_CHECKING needed


class ProductEnum(str, Enum):
    V = "virgin_product"
    R = "reman_product"


class ProductDetails(TypedDict):
    """
    Typed dictionary defining simulation parameters for a given product type.

    Attributes:
        advertising_effectiveness (float): Probability of a potential user being influenced to buy.
        wom_threshold (float): Threshold for word-of-mouth influence.
        wants_state (CustomerStatesEnum): State to represent the desire for this product.
        uses_state (CustomerStatesEnum): State to represent active usage of this product.
        buy_message (MessageType): Message type sent when attempting to buy this product.
    """

    wants_state: CustomerStatesEnum
    uses_state: CustomerStatesEnum
    buy_message: MessageType


product_params: dict[ProductEnum, ProductDetails] = {
    ProductEnum.V: {
        "wants_state": CustomerStatesEnum.WANTS_VIRGIN,
        "uses_state": CustomerStatesEnum.USES_VIRGIN,
        "buy_message": MessageType.BUY_V,
    },
    ProductEnum.R: {
        "wants_state": CustomerStatesEnum.WANTS_REMAN,
        "uses_state": CustomerStatesEnum.USES_REMAN,
        "buy_message": MessageType.BUY_R,
    },
}
