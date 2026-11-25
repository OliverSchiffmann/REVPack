import unittest, copy
import numpy as np
from reuman.customer import Customer, CustomerStatesEnum
from reuman.OEM import OEM
from reuman.product import ProductEnum
from reuman.world import World
from tests.test_scenarios import TEST_SCENARIOS


class TestMakeToStock(unittest.TestCase):
    """The make_to_stock production policy (OS direct re-order case)."""

    def setUp(self):
        self.rng = np.random.default_rng(42)
        self.config = copy.deepcopy(TEST_SCENARIOS["Default"])
        self.config["main"]["time_unit"] = "month"
        self.config["oem"]["production_policy"] = "make_to_stock"
        self.config["oem"]["virgin_stock"] = 0
        self.config["oem"]["reman_stock"] = 0
        self.config["oem"]["core_stock"] = 0

    def _make(self):
        world = World(config=self.config)
        oem = OEM(id=-1, world=world, config=self.config)
        customer = Customer(id=2, world=world, oem=oem, config=self.config)
        world.add_agents_from_list([oem, customer])
        return world, oem, customer

    def test_unknown_policy_raises(self):
        self.config["oem"]["production_policy"] = "just_in_time"
        with self.assertRaises(ValueError):
            self._make()

    def test_no_virgin_made_without_waiting_customers(self):
        _, oem, _ = self._make()
        oem.update_production()
        self.assertAlmostEqual(oem._factory_stock[ProductEnum.V], 0.0)

    def test_virgin_covers_only_what_stock_cannot(self):
        """10 customers waiting, 3 cores become reman units: 7 virgin units are made."""
        _, oem, _ = self._make()
        oem._core_stock = 3
        oem._num_to_man[ProductEnum.V] = 10
        oem.update_production()
        self.assertAlmostEqual(oem._factory_stock[ProductEnum.R], 3.0)
        self.assertAlmostEqual(oem._factory_stock[ProductEnum.V], 7.0)

    def test_waiting_customers_count_towards_virgin_only(self):
        world, oem, customer = self._make()
        customer.force_market_entry(self.rng, ProductEnum.V)  # nothing in stock: waits
        oem.update_manufacturing_counts()
        self.assertEqual(oem._num_to_man[ProductEnum.V], 1)
        self.assertEqual(oem._num_to_man[ProductEnum.R], 0)

    def test_every_core_is_remanufactured(self):
        _, oem, _ = self._make()
        oem._core_stock = 7
        oem.update_production()  # nobody wants reman, but the cores are used anyway
        self.assertAlmostEqual(oem._factory_stock[ProductEnum.R], 7.0)
        self.assertAlmostEqual(oem._core_stock, 0.0)

    def test_reman_first_then_virgin(self):
        _, oem, _ = self._make()
        oem._factory_stock[ProductEnum.V] = 1
        oem._factory_stock[ProductEnum.R] = 1
        first = oem.request_product(None)
        second = oem.request_product(None)
        assert first is not None and second is not None
        self.assertEqual(first.product, ProductEnum.R)
        self.assertEqual(second.product, ProductEnum.V)
        self.assertIsNone(oem.request_product(None))  # nothing left

    def test_new_customer_takes_reman_from_stock(self):
        """The demand profile says virgin, but the customer gets what is in stock."""
        self.config["oem"]["delivery_delay"] = 0
        _, oem, customer = self._make()
        oem._factory_stock[ProductEnum.R] = 1
        customer.force_market_entry(self.rng, ProductEnum.V)
        self.assertEqual(customer.state(), CustomerStatesEnum.USES_REMAN)

    def test_customer_waits_when_nothing_in_stock(self):
        _, _, customer = self._make()
        customer.force_market_entry(self.rng, ProductEnum.V)
        self.assertEqual(customer.state(), CustomerStatesEnum.WANTS_ANY)

    def test_make_to_order_is_the_default(self):
        del self.config["oem"]["production_policy"]
        _, oem, _ = self._make()
        self.assertFalse(oem.supplies_from_stock())


class TestStrategySetupCost(unittest.TestCase):

    def setUp(self):
        self.config = copy.deepcopy(TEST_SCENARIOS["Default"])
        self.buy_back = {
            "enabled": True,
            "bounty_value": 10.0,
            "return_rate_uplift": 0.1,
            "setup_cost": 70000.0,
        }

    def _oem(self):
        world = World(config=self.config)
        return OEM(id=-1, world=world, config=self.config)

    def test_setup_cost_paid_once_at_start(self):
        self.config["oem"]["collection_strategies"] = {"buy_back": self.buy_back}
        with_cost = self._oem()
        self.config["oem"]["collection_strategies"] = {}
        without = self._oem()
        self.assertAlmostEqual(without._balance - with_cost._balance, 70000.0)
        report = with_cost.generate_financial_report()
        self.assertEqual(
            report["Breakdown"]["Collection strategy set-up cost"], 70000.0
        )

    def test_no_setup_cost_without_reman(self):
        self.config["main"]["enable_reman"] = False
        self.config["oem"]["collection_strategies"] = {"buy_back": self.buy_back}
        self.assertEqual(self._oem()._strategy_setup_cost, 0.0)

    def test_negative_setup_cost_raises(self):
        self.buy_back["setup_cost"] = -1
        self.config["oem"]["collection_strategies"] = {"buy_back": self.buy_back}
        with self.assertRaises(ValueError):
            self._oem()


class TestWeibullShape(unittest.TestCase):

    def _customer(self, **overrides):
        config = copy.deepcopy(TEST_SCENARIOS["Default"])
        config["b2b_customer"].update(lifetime_method="weibull", **overrides)
        world = World(config=config)
        oem = OEM(id=-1, world=world, config=config)
        return Customer(id=2, world=world, oem=oem, config=config)

    def test_sample_mean_matches_mean_lifetime(self):
        """With no early failures, the draws average out to mean_lifetime for any shape."""
        rng = np.random.default_rng(1)
        for shape in (1.5, 2.9, 4.0):
            with self.subTest(shape=shape):
                c = self._customer(
                    mean_lifetime=3000, lifetime_shape=shape, early_failure_share=0.0
                )
                draws = [c.get_weibull_lifetime(rng) for _ in range(20000)]
                self.assertAlmostEqual(np.mean(draws) / 3000, 1.0, delta=0.02)

    def test_invalid_settings_raise(self):
        for overrides in ({"lifetime_shape": 0}, {"early_failure_share": 1.5}):
            with self.subTest(**overrides):
                with self.assertRaises(ValueError):
                    self._customer(**overrides)


if __name__ == "__main__":
    unittest.main()
