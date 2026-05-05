
"""
Module for the World agent.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from ._agent import AgentEnum, BaseAgent
import random
from .message import Message
import asyncio
from . import customer
from .product import ProductEnum


if TYPE_CHECKING:
    from .customer import Customer, CustomerStatesEnum
    from .OEM import OEM


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

    def get_agents(self) -> list[BaseAgent]:
        """
        Returns a list of all agents currently in the simulation.
        
        Returns:
            list[BaseAgent]: A list of all agents.
        """
        return list(self._agents.values())

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
                
        # Call OEM agents first (as they were originally added first)
        for oem_id in self._agents_by_type[AgentEnum.OEM]:
            self._agents[oem_id].next(rng)
            
        # Shuffle customer agents to prevent ordering bias for limited stock
        customer_ids = self._agents_by_type[AgentEnum.CUSTOMER][:]
        rng.shuffle(customer_ids)
        for cust_id in customer_ids:
            self._agents[cust_id].next(rng)

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

    async def run(self, rng, simulation_length: int, progress_callback=None) -> tuple[dict, dict]:
        """
        Executes the simulation loop for a specified number of ticks, 
        collects time-series results, and generates a final report.
        """
        # Find the OEM agent for data collection
        oem_id = self._agents_by_type[AgentEnum.OEM][0]
        oemAgent: OEM = self._agents[oem_id]  # type: ignore

        results = {
            "day": [], "potential_users": [], "wants_virgin": [], "uses_virgin": [],
            "wants_reman": [], "uses_reman": [], "wants_any": [], "waiting_for_delivery": [],
            "core_stock": [], "virgin_stock": [], "reman_stock": [], "virgin_sold": [],
            "reman_sold": [], "cores_collected": [], "cores_rejected": [], 
            "inspection_cost": [], "bounty_values_paid": [], "oem_balance": [],
        }

        for i in range(simulation_length):
            self.tick()
            
            # Record states
            results["day"].append(self.now())
            results["potential_users"].append(self._num_potential_users)
            results["wants_virgin"].append(self._num_wants[ProductEnum.V])
            results["uses_virgin"].append(self._num_uses[ProductEnum.V])
            results["wants_reman"].append(self._num_wants[ProductEnum.R])
            results["uses_reman"].append(self._num_uses[ProductEnum.R])
            results["wants_any"].append(self._num_wants_any)
            results["waiting_for_delivery"].append(self._num_waiting_for_delivery)
            
            # Fetch OEM specific data cleanly
            oem_metrics = oemAgent.get_tracking_metrics()
            for key, value in oem_metrics.items():
                results[key].append(value)

            self.call_next(rng)

            if progress_callback is not None:
                update_interval = max(1, simulation_length // 100)
                if i % update_interval == 0:
                    progress_callback(i, simulation_length)
                    await asyncio.sleep(0)

        report = oemAgent.generate_financial_report()
        return results, report
