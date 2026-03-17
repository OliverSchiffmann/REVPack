from __future__ import annotations
from typing import TYPE_CHECKING
from ._agent import AgentEnum, BaseAgent
import random
from .message import Message
from . import customer
from .product import ProductEnum


if TYPE_CHECKING:
    from .customer import Customer, CustomerStatesEnum
    from .OEM import OEM, OEMStatesEnum


class World:
    _now: int
    _agents: dict[int, BaseAgent]
    _agents_by_type: dict[AgentEnum, list[int]]
    _num_potential_users: int
    _num_wants: dict[ProductEnum, int]
    _num_uses: dict[ProductEnum, int]
    _num_wants_any: int
    _message_queue: list[Message]
    _active_products: list[ProductEnum]

    def __init__(self, enable_reman: bool = True) -> None:
        self._now = 0
        self._agents = {}
        self._agents_by_type = {AgentEnum.CUSTOMER: [], AgentEnum.OEM: []}
        self._num_potential_users = 0
        self._num_wants = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._num_uses = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._num_wants_any = 0
        self._num_to_man = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._message_queue = []
        self._active_products = [ProductEnum.V]
        if enable_reman:
            self._active_products.append(ProductEnum.R)

    def tick(self) -> None:
        self._now += 1
        self.update_customer_state_counts()

    def now(self) -> int:
        return self._now

    def get_active_products(self) -> list[ProductEnum]:
        return self._active_products[:]  # returns a copy to avoid editing

    def add_agent(self, agent: BaseAgent):
        if agent.id() in self._agents:
            exit(f"Agent with id already exists. Received: {agent.id}")
        self._agents[agent.id()] = agent
        self._agents_by_type[agent.type()].append(agent.id())

    def call_next(self, rng):
        for _, agent in self._agents.items():
            agent.next(rng)

    def update_customer_state_counts(self):
        from .customer import CustomerStatesEnum

        self._num_wants = {product: 0 for product in ProductEnum}
        self._num_uses = {product: 0 for product in ProductEnum}
        self._num_to_man = {product: 0 for product in ProductEnum}
        self._num_wants_any = 0
        potential_users = 0

        for agent in self._agents.values():
            if isinstance(agent, customer.Customer):
                if agent.state() == CustomerStatesEnum.POTENTIAL_USER:
                    potential_users += 1
                elif agent.state() == CustomerStatesEnum.WANTS_VIRGIN:
                    self._num_wants[ProductEnum.V] += 1
                    if agent._delivery_day != -1:
                        self._num_to_man[ProductEnum.V] += 1
                elif agent.state() == CustomerStatesEnum.USES_VIRGIN:
                    self._num_uses[ProductEnum.V] += 1
                elif agent.state() == CustomerStatesEnum.WANTS_REMAN:
                    self._num_wants[ProductEnum.R] += 1
                    self._num_to_man[ProductEnum.R] += 1
                elif agent.state() == CustomerStatesEnum.USES_REMAN:
                    self._num_uses[ProductEnum.R] += 1
                elif agent.state() == CustomerStatesEnum.WANTS_ANY:
                    self._num_wants_any += 1
                    self._num_to_man[ProductEnum.V] += 1
                    self._num_to_man[ProductEnum.R] += 1
        self._num_potential_users = potential_users

    def receive_message(self, message: Message):
        self._message_queue.append(message)

    def process_messages(self, rng):
        for message in self._message_queue:
            recipient = self._agents.get(message.recipient_id)
            if recipient:
                recipient.handle_message(message, rng)
        self._message_queue.clear()
