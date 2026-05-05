import unittest, copy
import numpy as np
import test
from reuman import world,customer
from reuman import world
from reuman._agent import BaseAgent, AgentEnum
from reuman.product import ProductEnum
from reuman.states import CustomerStatesEnum
from reuman.message import Message, MessageType
from reuman.OEM import OEM
from tests.test_scenarios import TEST_SCENARIOS
from reuman.customer import Customer


class TestWorld(unittest.TestCase):

    def setUp(self):
        self.test_config = copy.deepcopy(TEST_SCENARIOS["Default"])

    def test_now_func(self):
        testWorld = world.World(config=self.test_config)
        modelTimeStep = testWorld._now
        funcTimeStep = testWorld.now()
        self.assertEqual(modelTimeStep, funcTimeStep)

    def test_add_agent(self):
        # Test to see whether adding an agent actually adds the right agent with the right params
        testWorld = world.World(config=self.test_config)
        # testAgent = 
        testAgent = BaseAgent(world=testWorld, id=1, type=AgentEnum.OEM)
        testWorld.add_agent(testAgent)
        
        self.assertIn(1, testWorld._agents)
        self.assertIn(1, testWorld._agents_by_type[AgentEnum.OEM])

    def test_add_agents_from_list(self):
        testWorld = world.World(config=self.test_config)
        agents = [
            BaseAgent(world=testWorld, id=1, type=AgentEnum.CUSTOMER),
            BaseAgent(world=testWorld, id=2, type=AgentEnum.CUSTOMER)
        ]
        testWorld.add_agents_from_list(agents)
        
        self.assertEqual(len(testWorld._agents), 2)
        self.assertEqual(len(testWorld._agents_by_type[AgentEnum.CUSTOMER]), 2)

    def test_tick(self):
        testWorld = world.World(config=self.test_config)
        testWorld.tick()
        self.assertEqual(testWorld.now(), 1)

    def test_get_active_products(self):
        testWorld = world.World(config=self.test_config)
        products = testWorld.get_active_products()
        self.assertIn(ProductEnum.V, products)
        self.assertIn(ProductEnum.R, products)
        
        # Ensure that it returns a copy to prevent mutation bugs
        products.pop()
        self.assertNotEqual(len(products), len(testWorld.get_active_products()))

    def test_update_customer_state_counts(self):
        testWorld = world.World(config=self.test_config)
        # Create a mock OEM config to initialize Customers safely
        # Copy the config from the baseline scenario
        test_config = self.test_config
        oem = OEM(id=99, world=testWorld, config=test_config)
        
        c1 = Customer(id=1, world=testWorld, oem=oem, config=test_config, customer_type="b2b_customer")
        c1._state = CustomerStatesEnum.WANTS_VIRGIN
        
        c2 = Customer(id=2, world=testWorld, oem=oem, config=test_config, customer_type="b2b_customer")
        c2._state = CustomerStatesEnum.USES_REMAN
        
        testWorld.add_agents_from_list([c1, c2])
        testWorld.update_customer_state_counts()
        
        self.assertEqual(testWorld._num_wants[ProductEnum.V], 1)
        self.assertEqual(testWorld._num_uses[ProductEnum.R], 1)
        self.assertEqual(testWorld._num_wants[ProductEnum.R], 0)

    def test_message_queue(self):
        testWorld = world.World(config=self.test_config)
        msg = Message(sender_id=1, recipient_id=2, content=MessageType.BUY_V)
        testWorld.receive_message(msg)
        self.assertEqual(len(testWorld._message_queue), 1)
        
        # Process messages should clear the queue
        testWorld.process_messages(np.random.default_rng(42))
        self.assertEqual(len(testWorld._message_queue), 0)

    def test_generate_demand(self):
        """Test that deterministic demand correctly forces agents into the market."""
        test_config = copy.deepcopy(self.test_config)
        # Force deterministic demand to exactly 5 per day
        test_config["products"]["V"]["demand_profile"] = {"type": "deterministic", "amount_per_day": 5}
        test_config["products"]["R"]["demand_profile"] = {"type": "deterministic", "amount_per_day": 0}
        
        testWorld = world.World(config=test_config)
        oem = OEM(id=99, world=testWorld, config=test_config)
        
        customers = []
        for i in range(10):
            c = Customer(id=i, world=testWorld, oem=oem, config=test_config, customer_type="b2b_customer")
            c._state = CustomerStatesEnum.POTENTIAL_USER
            customers.append(c)
            
        testWorld.add_agents_from_list(customers)
        testWorld.add_agent(oem)
        
        testWorld.generate_demand(np.random.default_rng(42))
        
        # Check that exactly 5 customers transitioned out of the POTENTIAL_USER state
        market_entered_count = sum(1 for c in customers if c.state() != CustomerStatesEnum.POTENTIAL_USER)
        self.assertEqual(market_entered_count, 5)
    
if __name__ == "__main_":
    unittest.main()
