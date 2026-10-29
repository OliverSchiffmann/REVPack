import unittest, copy
import asyncio
import json
import os
import tempfile
from reuman import demand_inputs
from tests.test_demand_inputs import make_forecast
import numpy as np
import test
from reuman import world, customer
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
            BaseAgent(world=testWorld, id=2, type=AgentEnum.CUSTOMER),
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

        c1 = Customer(
            id=1,
            world=testWorld,
            oem=oem,
            config=test_config,
            customer_type="b2b_customer",
        )
        c1._state = CustomerStatesEnum.WANTS_VIRGIN

        c2 = Customer(
            id=2,
            world=testWorld,
            oem=oem,
            config=test_config,
            customer_type="b2b_customer",
        )
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
        test_config["products"]["V"]["demand_profile"] = {
            "type": "deterministic",
            "amount_per_day": 5,
        }
        test_config["products"]["R"]["demand_profile"] = {
            "type": "deterministic",
            "amount_per_day": 0,
        }

        testWorld = world.World(config=test_config)
        oem = OEM(id=99, world=testWorld, config=test_config)

        customers = []
        for i in range(10):
            c = Customer(
                id=i,
                world=testWorld,
                oem=oem,
                config=test_config,
                customer_type="b2b_customer",
            )
            c._state = CustomerStatesEnum.POTENTIAL_USER
            customers.append(c)

        testWorld.add_agents_from_list(customers)
        testWorld.add_agent(oem)

        testWorld.generate_demand(np.random.default_rng(42))

        # Check that exactly 5 customers transitioned out of the POTENTIAL_USER state
        market_entered_count = sum(
            1 for c in customers if c.state() != CustomerStatesEnum.POTENTIAL_USER
        )
        self.assertEqual(market_entered_count, 5)


class TestWorldForecastProfiles(unittest.TestCase):
    """Forecast demand profiles are turned into stochastic rates when a World is created."""

    def setUp(self):
        self.config = copy.deepcopy(TEST_SCENARIOS["Default"])
        self.config["main"]["B2B_population"] = 1000
        self.config["main"]["B2C_population"] = 0
        self.config["main"]["starting_customers"] = 200
        self.v_data = make_forecast([1, 0, 2, 1, 0, 1, 1], [1, 2, 1])
        self.r_data = make_forecast([0, 0, 1, 0, 0, 0, 0], [0, 0, 1])
        self.config["products"]["V"]["demand_profile"] = {
            "type": "forecast",
            "forecast": self.v_data,
        }
        self.config["products"]["R"]["demand_profile"] = {
            "type": "forecast",
            "forecast": self.r_data,
        }

    def test_forecasts_become_stochastic_rates(self):
        w = world.World(config=self.config)
        expected = demand_inputs.estimate_ad_rates(
            demand_inputs.build_daily_series(self.v_data),
            demand_inputs.build_daily_series(self.r_data),
            market_size=1000,
            starting_customers=200,
        )
        self.assertEqual(
            w._demand_profiles["V"], {"type": "stochastic", "rate": expected["V"]}
        )
        self.assertEqual(
            w._demand_profiles["R"], {"type": "stochastic", "rate": expected["R"]}
        )

    def test_config_is_not_changed(self):
        before = copy.deepcopy(self.config)
        world.World(config=self.config)
        self.assertEqual(self.config, before)

    def test_calibration_details_are_kept(self):
        cal = world.World(config=self.config).get_demand_calibration()
        self.assertEqual(set(cal), {"V", "R"})
        self.assertEqual(cal["V"]["start_date"], "2025-01-01")
        self.assertEqual(cal["V"]["end_date"], "2025-01-10")
        self.assertEqual(cal["V"]["history_days"], 7)
        self.assertEqual(cal["V"]["daily_values"], [1, 0, 2, 1, 0, 1, 1, 1, 2, 1])

    def test_file_path_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "v.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.v_data, f)
            self.config["products"]["V"]["demand_profile"]["forecast"] = path
            from_path = world.World(config=self.config)._demand_profiles["V"]
        self.config["products"]["V"]["demand_profile"]["forecast"] = self.v_data
        from_dict = world.World(config=self.config)._demand_profiles["V"]
        self.assertEqual(from_path, from_dict)

    def test_only_one_forecast(self):
        # R keeps its hand-typed stochastic rate; only V is calibrated
        self.config["products"]["R"]["demand_profile"] = {
            "type": "stochastic",
            "rate": 0.0003,
        }
        w = world.World(config=self.config)
        self.assertEqual(w._demand_profiles["V"]["type"], "stochastic")
        self.assertEqual(
            w._demand_profiles["R"], {"type": "stochastic", "rate": 0.0003}
        )
        self.assertEqual(set(w.get_demand_calibration()), {"V"})

    def test_no_forecasts_gives_empty_calibration(self):
        w = world.World(config=copy.deepcopy(TEST_SCENARIOS["Default"]))
        self.assertEqual(w.get_demand_calibration(), {})

    def test_reman_forecast_with_reman_disabled_raises(self):
        self.config["main"]["enable_reman"] = False
        with self.assertRaises(ValueError):
            world.World(config=self.config)

    def test_forecast_profile_without_data_raises(self):
        del self.config["products"]["V"]["demand_profile"]["forecast"]
        with self.assertRaises(ValueError):
            world.World(config=self.config)


class TestNewCustomerCounting(unittest.TestCase):
    """The World records how many customers enter the market each day."""

    def setUp(self):
        self.config = copy.deepcopy(TEST_SCENARIOS["Default"])
        self.config["products"]["V"]["demand_profile"] = {
            "type": "deterministic",
            "amount_per_day": 5,
        }
        self.config["products"]["R"]["demand_profile"] = {
            "type": "deterministic",
            "amount_per_day": 0,
        }

    def _world_with_customers(self, n):
        w = world.World(config=self.config)
        oem = OEM(id=99, world=w, config=self.config)
        customers = [
            Customer(
                id=i, world=w, oem=oem, config=self.config, customer_type="b2b_customer"
            )
            for i in range(n)
        ]
        w.add_agents_from_list(customers)
        w.add_agent(oem)
        return w

    def test_counts_new_customers(self):
        w = self._world_with_customers(10)
        w.generate_demand(np.random.default_rng(42))
        self.assertEqual(w._new_customers_today, {ProductEnum.V: 5, ProductEnum.R: 0})

    def test_count_resets_when_market_is_used_up(self):
        # 5 customers and 5 entries per day: day 1 uses everyone, day 2 has none left
        w = self._world_with_customers(5)
        rng = np.random.default_rng(42)
        w.generate_demand(rng)
        w.generate_demand(rng)
        self.assertEqual(w._new_customers_today, {ProductEnum.V: 0, ProductEnum.R: 0})

    def test_run_records_new_customers_each_day(self):
        w = self._world_with_customers(20)
        results, _ = asyncio.run(w.run(np.random.default_rng(1), simulation_length=6))
        self.assertEqual(len(results["new_customers_V"]), 6)
        self.assertEqual(len(results["new_customers_R"]), 6)
        # 5 a day until the 20 potential customers run out
        self.assertEqual(results["new_customers_V"], [5, 5, 5, 5, 0, 0])
        self.assertEqual(sum(results["new_customers_R"]), 0)


if __name__ == "__main__":
    unittest.main()
