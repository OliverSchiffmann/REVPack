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
        test_config = {
            'oem':{
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
                },
            'b2b_customer':{
                "patience": 10,
                "mean_lifetime": 200,
                "lifetime_method": "triangular",
                "lifetime_range": 50,
                "core_return_rate": 1.0,
                }
            }
        self.oem = OEM(id=-1, world=self.world, config=test_config)
        
        # Provide a baseline config for the customer
        self.cust_config = {
            "patience": 10,
            "mean_lifetime": 200,
            "lifetime_method": "triangular",
            "lifetime_range": 50,
            "core_return_rate": 1.0,
        }
        self.customer = Customer(id=2, world=self.world, oem=self.oem, config=test_config)
        
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
        self.oem._num_to_man[ProductEnum.V] = 10
        self.oem._num_to_man[ProductEnum.R] = 10
        self.oem.update_production()
        self.assertEqual(self.oem._production_rate[ProductEnum.V], 2)
        self.assertEqual(self.oem._production_rate[ProductEnum.R], 0)
        
        self.assertEqual(self.oem._factory_stock[ProductEnum.V], 12)
        self.assertEqual(self.oem._factory_stock[ProductEnum.R], 0)

    def test_update_production_cores(self):
        """ Test whether the production rates act as expected, with available cores."""

        self.oem._num_to_man[ProductEnum.V] = 10
        self.oem._num_to_man[ProductEnum.R] = 10
        self.oem._core_stock = 10
        self.oem.update_production()
        
        self.assertEqual(self.oem._production_rate[ProductEnum.V], 2)
        self.assertEqual(self.oem._production_rate[ProductEnum.R], 2.5)
        
        self.assertEqual(self.oem._factory_stock[ProductEnum.V], 12)
        self.assertEqual(self.oem._factory_stock[ProductEnum.R], 2.5)
        self.assertEqual(self.oem._core_stock, 7.5)

    def test_get_shipping_delay(self):
        """Test shipping delay calculation with and without distance matrix."""
        # Baseline no matrix (returns delivery_delay)
        self.assertEqual(self.oem.get_shipping_delay("Rome"), 1)
        
        # Add a distance matrix mapping
        self.oem._distance_matrix = {
            "Brescia": {
                "Rome": {"driving_hours": 16.0, "has_ferry": False},
                "Palermo": {"driving_hours": 20.0, "has_ferry": True}
            }
        }
        self.assertEqual(self.oem.get_shipping_delay("Rome"), 3) # 1 day + (16//8) = 3
        self.assertEqual(self.oem.get_shipping_delay("Palermo"), 4) # 1 day + (20//8) + 1 (ferry) = 4
        self.assertEqual(self.oem.get_shipping_delay("Brescia"), 1) # Same location

    def test_schedule_core_return(self):
        """Test that scheduling a core return adds to the incoming cores list."""
        current_time = self.world.now()
        self.oem.schedule_core_return("Rome")
        
        self.assertEqual(len(self.oem._incoming_cores), 1)
        expected_arrival = current_time + self.oem._delivery_delay
        self.assertEqual(self.oem._incoming_cores[0], (expected_arrival, "Rome"))

    def test_process_incoming_cores(self):
        """Test that incoming cores are processed once their arrival day is reached."""
        self.oem._incoming_cores.append((self.world.now(), "Rome")) # Arrives today
        self.oem._incoming_cores.append((self.world.now() + 5, "Milan")) # Arrives in future
        
        initial_cores = self.oem._core_stock
        self.oem.process_incoming_cores(self.rng) # Using our seeded rng
        
        # Rome should be processed, Milan should remain
        self.assertEqual(len(self.oem._incoming_cores), 1)
        self.assertEqual(self.oem._incoming_cores[0][1], "Milan")
        self.assertEqual(self.oem._core_stock, initial_cores + 1)

    def test_return_product_acceptance_and_rejection(self):
        """Test core acceptance and rejection logic, including storage limits."""
        class MockRNG:
            def __init__(self, val): self.val = val
            def random(self): return self.val
            
        self.oem._core_acceptance_rate = 0.5
        self.oem._core_storage_limit = 1
        self.oem._core_stock = 0
        
        # 1. Accept core (rng returns 0.1 < 0.5)
        self.oem.return_product(MockRNG(0.1))
        self.assertEqual(self.oem._core_stock, 1)
        self.assertEqual(self.oem._total_cores_collected, 1)
        
        # 2. Accept core but over capacity (rng returns 0.1 < 0.5)
        self.oem.return_product(MockRNG(0.1))
        self.assertEqual(self.oem._core_stock, 1) # unchanged
        self.assertEqual(self.oem._total_cores_over_capacity, 1)
        
        # 3. Reject core (rng returns 0.9 > 0.5)
        self.oem.return_product(MockRNG(0.9))
        self.assertEqual(self.oem._core_stock, 1) # unchanged
        self.assertEqual(self.oem._total_cores_rejected, 1)

    def test_generate_financial_report(self):
        """Test that the financial report contains all expected keys."""
        report = self.oem.generate_financial_report()
        self.assertIn("Total Cost", report)
        self.assertIn("Total Revenue", report)
        self.assertIn("Breakdown", report)
        self.assertIn("Statistics", report)
        self.assertIn("Total bounties paid", report["Breakdown"])
        self.assertIn("Virgin units sold", report["Statistics"])

if __name__ == "__main__":
    unittest.main()