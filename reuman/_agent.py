from __future__ import annotations
from enum import Enum
from typing import TYPE_CHECKING
from .message import Message

if TYPE_CHECKING:  # IDK what this does
    from .world import World


class AgentEnum(str, Enum):  # what does that mean 'enumeration'?
    CUSTOMER = "customer"
    OEM = "oem"


class BaseAgent:
    _world: World
    _id: int
    _type: AgentEnum
    _state: Enum  # type of state will depend on the agent type

    def __init__(self, world: World, id: int, type: AgentEnum):
        self._world = world
        self._id = id
        self._type = type

    def id(self) -> int:
        return self._id

    def state(self) -> Enum:
        return self._state

    def type(self) -> AgentEnum:
        return self._type

    def next(self, rng):
        return

    def handle_message(self, message: Message, rng):
        pass  # specific functionality overridden by specific agent type
