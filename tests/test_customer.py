import unittest
import numpy as np
from reuman.customer import Customer, CustomerStatesEnum, B2B_Customer, B2C_Customer
from reuman.world import World
from reuman.OEM import OEM
from reuman.product import ProductEnum


class TestCustomer(unittest.TestCase):

    def setUp(self):
        # Initialise a random number generator with a fixed seed for reproducible tests
        self.rng = np.random.default_rng(42)
        self.world = World(enable_reman=True)

        # Full config structure matching the new interface
        self.config = {
            "oem": {
                "delivery_delay": 1,
                "manufacture_delay": 5,
                "remanufacture_delay": 3,
                "virgin_stock": 10,
                "reman_stock": 0,
                "core_stock": 0,
                "unit_production_cost_V": 500.0,
                "unit_production_cost_R": 300.0,
                "core_acceptance_rate": 1.0,
                "core_collection_cost": 20,
                "core_disposal_cost": 20,
                "core_storage_cost": 0.5,
                "retail_price_V": 1000,
                "retail_price_R": 1000,
            },
            "b2b_customer": {
                "patience": 10,
                "mean_lifetime": 200,
                "lifetime_method": "triangular",
                "lifetime_range": 50,
                "core_return_rate": 1.0,
            },
            "b2c_customer": {
                "patience": -1,
                "mean_lifetime": 50,
                "lifetime_method": "uniform",
                "lifetime_range": 10,
                "core_return_rate": 0.5,
            },
            "products": {
                "V": {
                    "advertising_effectiveness": 0.0006,
                    "wom_threshold": 0.015,
                },
                "R": {
                    "advertising_effectiveness": 0.0003,
                    "wom_threshold": 0.015,
                    "cores_consumed": 1,
                },
            },
        }
        self.oem = OEM(id=-1, world=self.world, config=self.config)
        self.customer = Customer(
            id=2,
            world=self.world,
            oem=self.oem,
            config=self.config,
            customer_type="b2b_customer",
        )

    def test_init(self):
        """Test that the Customer correctly maps its ID, state, and patience."""
        self.assertEqual(self.customer.id(), 2)
        self.assertEqual(self.customer.state(), CustomerStatesEnum.POTENTIAL_USER)
        self.assertEqual(self.customer._patience, 10)

    def test_become_user(self):
        """Test transition to become a user, and check that a lifespan is assigned."""
        self.customer.become_user(self.rng, ProductEnum.V)
        self.assertEqual(self.customer.state(), CustomerStatesEnum.USES_VIRGIN)
        self.assertEqual(self.customer._active_product, ProductEnum.V)
        self.assertNotEqual(self.customer._end_of_life_day, -1)

    def test_try_buy_with_stock(self):
        """Test purchasing when the OEM has stock and zero delivery delay, means we don't have to do a 'next()' call."""
        # The OEM is set up with 10 units of Virgin stock in setUp
        self.oem._delivery_delay = 0
        self.customer.try_and_buy(self.rng, ProductEnum.V)

        self.assertEqual(self.customer.state(), CustomerStatesEnum.USES_VIRGIN)
        self.assertEqual(
            self.oem._factory_stock[ProductEnum.V], 9
        )  # 1 unit should be deducted

    def test_try_buy_no_stock(self):
        """Test purchasing when the OEM is out of stock, scheduling patience timeout."""
        # Deplete OEM stock entirely
        self.oem._factory_stock[ProductEnum.V] = 0
        self.customer._state = CustomerStatesEnum.WANTS_VIRGIN
        self.customer._active_product = ProductEnum.V
        self.customer.try_and_buy(self.rng, ProductEnum.V)

        self.assertEqual(self.customer.state(), CustomerStatesEnum.WANTS_VIRGIN)
        self.assertNotEqual(
            self.customer._end_of_patience_day, -1
        )  # Patience timeout should be scheduled

    def test_uniform_lifetime(self):
        """Test that the uniform lifetime generator operates within expected boundaries."""
        self.customer._lifetime_method = "uniform"
        lifetime = self.customer.get_uniform_lifetime(self.rng)
        
        mean = self.customer._mean_lifetime
        variation = self.customer._lifetime_range
        self.assertTrue(mean - variation <= lifetime < mean + variation)

    def test_triangular_lifetime(self):
        """Test that the triangular lifetime generator falls within expected bounds."""
        self.customer._lifetime_method = "triangular"
        lifetime = self.customer.get_triangular_lifetime(self.rng)
        
        mean = self.customer._mean_lifetime
        variation = self.customer._lifetime_range
        self.assertTrue(mean - variation <= lifetime <= mean + variation)

    # Weibull doesn't behave like the others so is basically impossible to test simply.

    def test_handle_active_user_end_of_life(self):
        """Test that reaching end-of-life shifts state to WANTS_REMAN for the retained active product."""
        self.customer.become_user(self.rng, ProductEnum.R)
        self.customer._end_of_life_day = (
            self.world.now()
        )  # Force product end-of-life on current tick

        self.customer._handle_active_user(self.rng)
        self.assertEqual(self.customer.state(), CustomerStatesEnum.WANTS_REMAN)
        self.assertEqual(self.customer._delivery_day, -1)
        self.assertEqual(self.customer._end_of_life_day, -1)

    def test_handle_potential_user(self):
        """Test that a potential user transitions correctly based on advertising effectiveness."""
        # Force 100% ad effectiveness for Virgin product
        self.config["products"]["V"]["advertising_effectiveness"] = 1.0
        self.config["products"]["R"]["advertising_effectiveness"] = 0.0
        self.oem._delivery_delay = 0  # Instant delivery to jump straight to USES_VIRGIN
        
        self.customer._handle_potential_user(self.rng)
        
        self.assertEqual(self.customer.state(), CustomerStatesEnum.USES_VIRGIN)
        self.assertEqual(self.customer._active_product, ProductEnum.V)

    def test_handle_waiting_customer_delivery_arrives(self):
        """Test that a waiting customer receives their delivery on the delivery day."""
        self.customer._state = CustomerStatesEnum.WAITING_FOR_DELIVERY
        self.customer._active_product = ProductEnum.V
        self.customer._delivery_day = self.world.now()  # Delivery arrives today
        
        self.customer._handle_waiting_customer(self.rng)
        
        self.assertEqual(self.customer.state(), CustomerStatesEnum.USES_VIRGIN)
        self.assertEqual(self.customer._delivery_day, -1)

    def test_handle_waiting_customer_patience_expires(self):
        """Test that a waiting customer changes state to WANTS_ANY when patience runs out."""
        self.customer._state = CustomerStatesEnum.WANTS_VIRGIN
        self.customer._active_product = ProductEnum.V
        self.customer._delivery_day = -1
        self.customer._end_of_patience_day = self.world.now()  # Patience expires today
        
        self.customer._handle_waiting_customer(self.rng)
        
        self.assertEqual(self.customer.state(), CustomerStatesEnum.WANTS_ANY)

    def test_initialise_as_active_user(self):
        """Test that a customer can be initialised with a random remaining lifespan."""
        self.customer.initialise_as_active_user(self.rng, ProductEnum.R)
        
        self.assertEqual(self.customer.state(), CustomerStatesEnum.USES_REMAN)
        self.assertEqual(self.customer._active_product, ProductEnum.R)
        self.assertTrue(self.customer._end_of_life_day > self.world.now())

    def test_b2b_b2c_subclasses(self):
        """Test that B2B and B2C customers correctly load their specific configurations."""
        b2b = B2B_Customer(id=3, world=self.world, oem=self.oem, config=self.config)
        self.assertEqual(b2b._customer_config["mean_lifetime"], 200)
        self.assertEqual(b2b._patience, 10)
        
        b2c = B2C_Customer(id=4, world=self.world, oem=self.oem, config=self.config)
        self.assertEqual(b2c._customer_config["mean_lifetime"], 50)
        self.assertEqual(b2c._patience, -1)

    def test_handle_active_user_core_return(self):
        """Test that reaching end-of-life for a product triggers a core return scheduling."""
        self.customer.become_user(self.rng, ProductEnum.R)
        self.customer._end_of_life_day = self.world.now()
        self.customer._core_return_rate = 1.0  # Guarantee return
        
        initial_incoming = len(self.oem._incoming_cores)
        self.customer._handle_active_user(self.rng)
        
        # Should schedule 1 core return to the OEM
        self.assertEqual(len(self.oem._incoming_cores), initial_incoming + 1)

    def test_handle_active_user_core_not_returned(self):
        """Test that reaching end-of-life and not returning a core records it with the OEM."""
        self.customer.become_user(self.rng, ProductEnum.R)
        self.customer._end_of_life_day = self.world.now()
        self.customer._core_return_rate = 0.0  # Guarantee NO return
        
        initial_not_collected = self.oem._total_cores_not_collected
        self.customer._handle_active_user(self.rng)
        
        # Should record 1 uncollected core with the OEM
        self.assertEqual(self.oem._total_cores_not_collected, initial_not_collected + 1)

if __name__ == "__main__":
    unittest.main()
