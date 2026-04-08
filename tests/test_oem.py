import unittest
import numpy as np
from reuman.customer import Customer, CustomerStatesEnum
from reuman.world import World
from reuman.OEM import OEM, OEMStatesEnum
from reuman.product import ProductEnum


class TestOEM(unittest.TestCase):
    
    def setUp(self) -> None:
        
        # Initialise a random number generator with a fixed seed for reproducible tests
        self.rng = np.random.default_rng(42)
        self.world = World(enable_reman=True)
        
        # Copy the config from the baseline scenario
        self.oem_config = {
            "delivery_delay": 1,
            "manufacture_delay": 5,
            "remanufacture_delay": 4,
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
        """Test that the OEM correctly maps its parameters."""
        self.assertEqual(self.oem.id(), -1)
        self.assertEqual(self.oem.state(), OEMStatesEnum.OPERATIONAL)
        self.assertEqual(self.oem._delivery_delay, 1)
        self.assertEqual(self.oem._manufacture_delay, 5)
        self.assertEqual(self.oem._remanufacture_delay, 4)
        self.assertEqual(self.oem._factory_stock[ProductEnum.V], 10)
        self.assertEqual(self.oem._factory_stock[ProductEnum.R], 0)
        self.assertEqual(self.oem._core_stock, 0)
        self.assertEqual(self.oem._core_acceptance_rate, 1.0)
        self.assertEqual(self.oem._total_cores_collected, 0)
        self.assertEqual(self.oem._total_cores_rejected, 0)
        self.assertEqual(self.oem._total_cores_not_collected, 0)
        self.assertEqual(self.oem._unit_production_cost_V, 500.0)
        self.assertEqual(self.oem._unit_production_cost_R, 300.0)   
    
    def test_request_product_has_stock(self):
        """Test the OEMs behaviour when a customer requests something in stock."""
        self.oem._factory_stock[ProductEnum.V] = 1
        self.assertTrue(self.oem.request_product(ProductEnum.V))
        self.assertEqual(self.oem._factory_stock[ProductEnum.V], 0)
        self.assertEqual(self.oem._products_sold[ProductEnum.V], 1)

    def test_request_product_no_stock(self):
        """ Test the OEMs behaviour when a customer requests something out of stock."""
        self.oem._factory_stock[ProductEnum.V] = 0
        self.assertFalse(self.oem.request_product(ProductEnum.V))
        self.assertEqual(self.oem._factory_stock[ProductEnum.V], 0)
        self.assertEqual(self.oem._products_sold[ProductEnum.V], 0)
    
    def test_update_production_no_cores(self):
        """ Test whether the production rates act as expected, assuming baseline no cores."""
        self.oem._world._num_to_man[ProductEnum.V] = 10
        self.oem._world._num_to_man[ProductEnum.R] = 10
        self.oem.update_production()
        self.assertEqual(self.oem._production_rate[ProductEnum.V], 2)
        self.assertEqual(self.oem._production_rate[ProductEnum.R], 0)
        
        self.assertEqual(self.oem._factory_stock[ProductEnum.V], 12)
        self.assertEqual(self.oem._factory_stock[ProductEnum.R], 0)

    def test_update_production_cores(self):
        """ Test whether the production rates act as expected, with available cores."""

        self.oem._world._num_to_man[ProductEnum.V] = 10
        self.oem._world._num_to_man[ProductEnum.R] = 10
        self.oem._core_stock = 10
        self.oem.update_production()
        
        self.assertEqual(self.oem._production_rate[ProductEnum.V], 2)
        self.assertEqual(self.oem._production_rate[ProductEnum.R], 2.5)
        
        self.assertEqual(self.oem._factory_stock[ProductEnum.V], 12)
        self.assertEqual(self.oem._factory_stock[ProductEnum.R], 2.5)
        self.assertEqual(self.oem._core_stock, 7.5)

if __name__ == "__main__":
    unittest.main()