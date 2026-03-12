from enum import Enum
from dataclasses import dataclass


class MessageType(str, Enum):
    BUY_V = "buy_virgin_product"
    BUY_R = "buy_reman_product"


@dataclass
class Message:
    sender_id: int
    recipient_id: int
    content: MessageType
