
"""
Module for the World agent.
"""

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
    
    """
    World agent.

    The World agent is the backbone of the simulation, managing the clock, agents, and global state tracking. It allows for the communication between agents and stores the properties of the simulation world.

    """
    
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
        
        """
        Initialise the World agent.

        Args:
            id (int): Unique id for the agent.
            enable_reman (bool): Boolean to tell whether remanufactured products are available in the simulation.
        """
        
        self._now = 0
        self._agents = {}
        self._agents_by_type = {AgentEnum.CUSTOMER: [], AgentEnum.OEM: []}
        self._num_potential_users = 0
        self._num_wants = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._num_uses = {ProductEnum.V: 0, ProductEnum.R: 0}
        self._num_wants_any = 0
        self._message_queue = []
        self._active_products = [ProductEnum.V]
        if enable_reman:
            self._active_products.append(ProductEnum.R)

    def tick(self) -> None:
        
        """
        Moves the simulation on to the next time step and updates the stored states of the customers.
        """
        
        self._now += 1
        self.update_customer_state_counts()

    def now(self) -> int:
        """
        Returns the current time step of the simulation.
        
        Returns:
            int: The current time step.
        """
        return self._now

    def get_active_products(self) -> list[ProductEnum]:
        """
        Returns a copy of the list of active products in the simulation.
        
        Returns:
            list[ProductEnum]: A copy of the list of active products.
        """
        return self._active_products[:]  # returns a copy to avoid editing

    def add_agent(self, agent: BaseAgent):
        """
        Adds an agent to the simulation world.

        Args:
            agent (BaseAgent): The agent to be added.
        """
        if agent.id() in self._agents:
            exit(f"Agent with id already exists. Received: {agent.id}")
        self._agents[agent.id()] = agent
        self._agents_by_type[agent.type()].append(agent.id())
        
    def add_agents_from_list(self, agents: list[BaseAgent]):
        
        """
        Adds a list of agents to the simulation world.

        Args:
            agents (list[BaseAgent]): A list of agents to be added.
        """
        
        for agent in agents:
            self.add_agent(agent)

    def call_next(self, rng):
        
        """
        Calls the next function for each of the agents in the simulation.

        Args:
            rng (numpy.random.Generator): Random number generator.
        """
                
        for _, agent in self._agents.items():
            agent.next(rng)

    def update_customer_state_counts(self):
        
        """
        Updates the counts for all the customer states in the simulation.
        """
                
        from .customer import CustomerStatesEnum

        self._num_wants = {product: 0 for product in ProductEnum}
        self._num_uses = {product: 0 for product in ProductEnum}
        self._num_wants_any = 0
        self._num_waiting_for_delivery = 0
        potential_users = 0

        for agent in self._agents.values():
            if isinstance(agent, customer.Customer):
                if agent.state() == CustomerStatesEnum.POTENTIAL_USER:
                    potential_users += 1
                elif agent.state() == CustomerStatesEnum.WANTS_VIRGIN:
                    self._num_wants[ProductEnum.V] += 1
                elif agent.state() == CustomerStatesEnum.USES_VIRGIN:
                    self._num_uses[ProductEnum.V] += 1
                elif agent.state() == CustomerStatesEnum.WANTS_REMAN:
                    self._num_wants[ProductEnum.R] += 1
                elif agent.state() == CustomerStatesEnum.USES_REMAN:
                    self._num_uses[ProductEnum.R] += 1
                elif agent.state() == CustomerStatesEnum.WANTS_ANY:
                    self._num_wants_any += 1
                elif agent.state() == CustomerStatesEnum.WAITING_FOR_DELIVERY:
                    self._num_waiting_for_delivery += 1
               
        self._num_potential_users = potential_users

    def receive_message(self, message: Message):
        
        """
        Adds a message to the message queue.

        Args:
            message (Message): The message to be added.
        """
        
        self._message_queue.append(message)

    def process_messages(self, rng):
        
        """
        Deals with all of the messages in the queue. Sending them to the appropriate agent and telling that agent to process the message.

        Args:
            rng (numpy.random.Generator): Random number generator.
        """
        
        for message in self._message_queue:
            recipient = self._agents.get(message.recipient_id)
            if recipient:
                recipient.handle_message(message, rng)
        self._message_queue.clear()
