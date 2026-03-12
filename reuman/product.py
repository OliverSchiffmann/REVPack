from enum import Enum


class ProductEnum(str, Enum):
    V = "virgin_product"
    R = "reman_product"
