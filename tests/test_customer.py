import unittest
import numpy as np
from reuman.customer import Customer, CustomerStatesEnum
from reuman.world import World
from reuman.OEM import OEM
from reuman.product import ProductEnum

class TestCustomer(unittest.TestCase):

    def setUp(self):
        # Initialise a random number generator with a fixed seed for reproducible tests
        self.rng = np.random.default_rng(42)
        self.world = World(enable_reman=True)
        
        # Copy the config from the baseline scenario
        self.oem_config = {
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
            "retail_price_V": 1000,
            "retail_price_R": 1000,
        }
        self.oem = OEM(id=-1, world=self.world, config=self.oem_config)
        
        # Provide a baseline config for the customer
        self.cust_config = {
            "patience": 10,
            "mean_lifetime": 200,
            "lifetime_method": "triangular",
            "lifetime_range": 50,
            "core_return_rate": 1.0,
        }
        self.customer = Customer(id=2, world=self.world, oem=self.oem, config=self.cust_config)

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
        """Test purchasing when the OEM has stock and zero delivery delay."""
        # The OEM is set up with 10 units of Virgin stock in setUp
        self.customer.try_and_buy(self.rng, ProductEnum.V)
        
        self.assertEqual(self.customer.state(), CustomerStatesEnum.USES_VIRGIN)
        self.assertEqual(self.oem._factory_stock[ProductEnum.V], 9)  # 1 unit should be deducted

    def test_try_buy_no_stock(self):
        """Test purchasing when the OEM is out of stock, shifting the customer to a waiting state."""
        # Deplete OEM stock entirely
        self.oem._factory_stock[ProductEnum.V] = 0
        self.customer.try_and_buy(self.rng, ProductEnum.V)
        
        self.assertEqual(self.customer.state(), CustomerStatesEnum.WANTS_VIRGIN)
        self.assertNotEqual(self.customer._end_of_patience_day, -1) # Patience timeout should be scheduled

    def test_uniform_lifetime(self):
        """Test that the uniform lifetime generator operates within expected boundaries."""
        self.customer._config["lifetime_method"] = "uniform"
        lifetime = self.customer.get_uniform_lifetime(self.rng)
        
        mean = self.customer._config["mean_lifetime"]
        variation = self.customer._config.get("lifetime_range", 3)
        self.assertTrue(mean - variation <= lifetime < mean + variation)

    def test_triangular_lifetime(self):
        """Test that the triangular lifetime generator falls within expected bounds."""
        self.customer._config["lifetime_method"] = "triangular"
        lifetime = self.customer.get_triangular_lifetime(self.rng)
        
        mean = self.customer._config["mean_lifetime"]
        variation = self.customer._config.get("lifetime_range", 3)
        self.assertTrue(mean - variation <= lifetime <= mean + variation)
        
    def test_weibull_lifetime(self):
        """Test that the Weibull lifetime generator falls within expected bounds."""
        self.customer._config["lifetime_method"] = "weibull"
        lifetime = self.customer.get_weibull_lifetime(self.rng)
        
        mean = self.customer._config["mean_lifetime"]
        variation = self.customer._config.get("lifetime_range", 3)
        self.assertTrue(mean - variation <= lifetime <= mean + variation)

    def test_handle_active_user_end_of_life(self):
        """Test that reaching end-of-life drops the customer's active product and shifts their state."""
        self.customer.become_user(self.rng, ProductEnum.R)
        self.customer._end_of_life_day = self.world.now()  # Force product end-of-life on current tick
        
        self.customer._handle_active_user(self.rng)
        self.assertEqual(self.customer.state(), CustomerStatesEnum.WANTS_ANY)
        self.assertIsNone(self.customer._active_product)
        self.assertEqual(self.customer._delivery_day, -1)
        self.assertEqual(self.customer._end_of_life_day, -1)

if __name__ == "__main__":
    unittest.main()