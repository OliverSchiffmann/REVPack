from enum import Enum


class CustomerStatesEnum(str, Enum):
    POTENTIAL_USER = "potential_user"
    WANTS_VIRGIN = "wants_virgin"
    USES_VIRGIN = "uses_virgin"
    WANTS_REMAN = "wants_reman"
    USES_REMAN = "uses_reman"
    WANTS_ANY = "wants_any"
    WAITING_FOR_DELIVERY = "waiting_for_delivery"
