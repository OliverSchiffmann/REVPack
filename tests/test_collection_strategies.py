import unittest, copy
import numpy as np
from reuman._agent import AgentEnum
from reuman.collection_strategies import (
    STRATEGY_REGISTRY,
    BuyBack,
    CollectionStrategy,
    Contract,
    ContractKind,
    Lease,
    build_strategies,
)
from reuman.customer import Customer
from reuman.model_time_converter import ModelTimeConverter
from reuman.OEM import OEM
from reuman.product import ProductEnum
from reuman.world import World
from tests.test_scenarios import TEST_SCENARIOS


class _HalveCost(CollectionStrategy):
    """Test-only strategy: halves the collection cost."""

    name = "halve_cost"

    def collection_cost(self, contract, cost):
        return cost * 0.5


class _MinusTen(CollectionStrategy):
    """Test-only strategy: takes 10 off the collection cost. Clashes with 'clash'."""

    name = "minus_ten"
    incompatible_with = frozenset({"clash"})

    def collection_cost(self, contract, cost):
        return cost - 10


class _Clash(CollectionStrategy):
    name = "clash"


class _ThirdPartyOnly(CollectionStrategy):
    name = "third_party_only"
    allowed_operators = frozenset()  # no operator type may run it


class _FixedTerm(CollectionStrategy):
    """Test-only strategy: every contract runs for exactly 5 steps."""

    name = "fixed_term"

    def offer_contract(self, contract):
        return type(contract)(
            kind=contract.kind,
            operator=contract.operator,
            product=contract.product,
            term_steps=5,
        )


TEST_STRATEGIES = [_HalveCost, _MinusTen, _Clash, _ThirdPartyOnly, _FixedTerm]


class TestBuildStrategies(unittest.TestCase):

    def setUp(self):
        # Register the test-only strategies, and remove them again after each test
        for cls in TEST_STRATEGIES:
            STRATEGY_REGISTRY[cls.name] = cls
        self.addCleanup(self._unregister)
        self.tc = ModelTimeConverter.from_config(TEST_SCENARIOS["Default"])

    def _unregister(self):
        for cls in TEST_STRATEGIES:
            STRATEGY_REGISTRY.pop(cls.name, None)

    def test_empty_config_gives_no_strategies(self):
        self.assertEqual(build_strategies({}, AgentEnum.OEM, self.tc), [])

    def test_disabled_strategy_is_skipped(self):
        cfg = {"halve_cost": {"enabled": False}}
        self.assertEqual(build_strategies(cfg, AgentEnum.OEM, self.tc), [])

    def test_enabled_strategies_kept_in_config_order(self):
        cfg = {"minus_ten": {"enabled": True}, "halve_cost": {"enabled": True}}
        names = [s.name for s in build_strategies(cfg, AgentEnum.OEM, self.tc)]
        self.assertEqual(names, ["minus_ten", "halve_cost"])

    def test_unknown_strategy_raises(self):
        with self.assertRaises(ValueError):
            build_strategies(
                {"no_such_thing": {"enabled": True}}, AgentEnum.OEM, self.tc
            )

    def test_operator_not_allowed_raises(self):
        with self.assertRaises(ValueError):
            build_strategies(
                {"third_party_only": {"enabled": True}}, AgentEnum.OEM, self.tc
            )

    def test_incompatible_strategies_raise(self):
        cfg = {"minus_ten": {"enabled": True}, "clash": {"enabled": True}}
        with self.assertRaises(ValueError):
            build_strategies(cfg, AgentEnum.OEM, self.tc)

    def test_incompatible_but_disabled_is_fine(self):
        cfg = {"minus_ten": {"enabled": True}, "clash": {"enabled": False}}
        self.assertEqual(len(build_strategies(cfg, AgentEnum.OEM, self.tc)), 1)


class TestOEMWithStrategies(unittest.TestCase):

    def setUp(self):
        for cls in TEST_STRATEGIES:
            STRATEGY_REGISTRY[cls.name] = cls
        self.addCleanup(
            lambda: [STRATEGY_REGISTRY.pop(c.name, None) for c in TEST_STRATEGIES]
        )
        self.rng = np.random.default_rng(42)
        self.config = copy.deepcopy(TEST_SCENARIOS["Default"])

    def _make(self, strategies: dict, enable_reman: bool = True):
        self.config["main"]["enable_reman"] = enable_reman
        self.config["oem"]["collection_strategies"] = strategies
        world = World(config=self.config)
        oem = OEM(id=-1, world=world, config=self.config)
        customer = Customer(id=2, world=world, oem=oem, config=self.config)
        return world, oem, customer

    def test_no_strategies_gives_owned_contract(self):
        _, oem, _ = self._make({})
        contract = oem.contract_for(ProductEnum.V)
        self.assertEqual(contract.kind, ContractKind.OWNED)
        self.assertIs(contract.operator, oem)
        self.assertIsNone(contract.term_steps)
        self.assertEqual(contract.fee_per_step, 0.0)

    def test_request_product_returns_contract(self):
        _, oem, _ = self._make({})
        oem._factory_stock[ProductEnum.V] = 1
        contract = oem.request_product(ProductEnum.V)
        assert contract is not None
        self.assertEqual(contract.product, ProductEnum.V)
        self.assertIsNone(oem.request_product(ProductEnum.V))  # now out of stock

    def test_strategies_applied_in_order(self):
        """(20 - 10) * 0.5 = 5, whereas (20 * 0.5) - 10 = 0."""
        _, oem, _ = self._make(
            {"minus_ten": {"enabled": True}, "halve_cost": {"enabled": True}}
        )
        oem._core_collection_cost = 20
        oem.return_product(self.rng)
        self.assertEqual(oem._total_core_collection_cost, 5)

    def test_strategies_ignored_without_reman(self):
        _, oem, _ = self._make({"halve_cost": {"enabled": True}}, enable_reman=False)
        self.assertEqual(oem._strategies, [])

    def test_fixed_term_contract_sets_end_of_life(self):
        world, _, customer = self._make({"fixed_term": {"enabled": True}})
        customer.become_user(self.rng, ProductEnum.V)
        self.assertEqual(customer._end_of_life_step, world.now() + 5)

    def test_contract_cleared_at_end_of_life(self):
        world, _, customer = self._make({})
        customer.become_user(self.rng, ProductEnum.R)
        self.assertIsNotNone(customer._contract)
        customer._end_of_life_step = world.now()
        customer._handle_active_user(self.rng)
        self.assertIsNone(customer._contract)

    def test_returned_core_carries_its_contract(self):
        world, oem, customer = self._make({})
        customer.become_user(self.rng, ProductEnum.R)
        contract = customer._contract
        customer._core_return_rate = 1.0
        customer._end_of_life_step = world.now()
        customer._handle_active_user(self.rng)
        self.assertIs(oem._incoming_cores[-1].contract, contract)


class _MockRNG:
    """Returns a fixed number, so acceptance (draw < rate) is decided by the test."""

    def __init__(self, val):
        self.val = val

    def random(self):
        return self.val


class TestBuyBack(unittest.TestCase):

    def setUp(self):
        self.config = copy.deepcopy(TEST_SCENARIOS["Default"])
        self.tc = ModelTimeConverter.from_config(self.config)
        self.params = {"enabled": True, "bounty_value": 10.0, "return_rate_uplift": 0.1}

    def _oem(self, buy_back_params: dict | None):
        strategies = {} if buy_back_params is None else {"buy_back": buy_back_params}
        self.config["oem"]["collection_strategies"] = strategies
        world = World(config=self.config)
        oem = OEM(id=-1, world=world, config=self.config)
        oem._core_acceptance_rate = 0.5
        return oem

    def test_missing_param_raises(self):
        with self.assertRaises(ValueError):
            build_strategies(
                {"buy_back": {"enabled": True, "bounty_value": 10.0}},
                AgentEnum.OEM,
                self.tc,
            )

    def test_invalid_params_raise(self):
        for key, bad in (("bounty_value", -1.0), ("return_rate_uplift", 1.5)):
            with self.subTest(key=key):
                params = dict(self.params, **{key: bad})
                with self.assertRaises(ValueError):
                    BuyBack(params, self.tc)

    def test_uplift_added_for_owners_and_capped(self):
        bb = BuyBack(self.params, self.tc)
        self.assertAlmostEqual(bb.return_probability(None, 0.8), 0.9)
        self.assertEqual(bb.return_probability(None, 0.95), 1.0)

    def test_no_uplift_or_payment_for_leased_products(self):
        bb = BuyBack(self.params, self.tc)
        oem = self._oem(None)
        leased = Contract(kind=ContractKind.LEASED, operator=oem, product=ProductEnum.V)
        self.assertEqual(bb.return_probability(leased, 0.8), 0.8)
        self.assertEqual(bb.acquisition_cost(leased, 0.0), 0.0)

    def test_bounty_paid_on_accepted_core_only(self):
        oem = self._oem(self.params)
        oem.return_product(_MockRNG(0.9))  # rejected (0.9 >= 0.5)
        self.assertEqual(oem._total_acquisition_cost, 0.0)
        oem.return_product(_MockRNG(0.1))  # accepted (0.1 < 0.5)
        self.assertEqual(oem._total_acquisition_cost, 10.0)

    def test_bounty_reduces_balance(self):
        """Same accepted core with and without buy-back: balances differ by the bounty."""
        with_bb = self._oem(self.params)
        without_bb = self._oem(dict(self.params, enabled=False))
        with_bb.return_product(_MockRNG(0.1))
        without_bb.return_product(_MockRNG(0.1))
        self.assertAlmostEqual(without_bb._balance - with_bb._balance, 10.0)

    def test_oem_applies_uplift(self):
        oem = self._oem(self.params)
        self.assertAlmostEqual(oem.core_return_probability(None, 0.8), 0.9)

    def test_no_payment_when_disabled(self):
        oem = self._oem(dict(self.params, enabled=False))
        oem.return_product(_MockRNG(0.1))
        self.assertEqual(oem._total_acquisition_cost, 0.0)

    def test_old_bounty_value_key_raises(self):
        self.config["oem"]["bounty_value"] = 10.0
        with self.assertRaises(ValueError):
            OEM(id=-1, world=World(config=self.config), config=self.config)


class TestLease(unittest.TestCase):

    def setUp(self):
        self.rng = np.random.default_rng(42)
        self.config = copy.deepcopy(TEST_SCENARIOS["Default"])
        self.params = {
            "enabled": True,
            "lease_period": 12,
            "monthly_fee_V": 70.0,
            "monthly_fee_R": 55.0,
            "acceptance_uplift": 0.15,
            "collection_cost_saving": 0.25,
        }

    def _make(self, time_unit: str = "day", strategies: dict | None = None):
        self.config["main"]["time_unit"] = time_unit
        self.config["oem"]["collection_strategies"] = (
            {"lease": self.params} if strategies is None else strategies
        )
        world = World(config=self.config)
        oem = OEM(id=-1, world=world, config=self.config)
        customer = Customer(id=2, world=world, oem=oem, config=self.config)
        world.add_agents_from_list([oem, customer])
        return world, oem, customer

    def test_invalid_params_raise(self):
        tc = ModelTimeConverter.from_config(self.config)
        for key, bad in (
            ("lease_period", 0.5),
            ("monthly_fee_V", -1.0),
            ("acceptance_uplift", 1.5),
            ("collection_cost_saving", -0.1),
        ):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    Lease(dict(self.params, **{key: bad}), tc)

    def test_cannot_combine_with_buy_back(self):
        tc = ModelTimeConverter.from_config(self.config)
        strategies = {
            "buy_back": {
                "enabled": True,
                "bounty_value": 10.0,
                "return_rate_uplift": 0.1,
            },
            "lease": self.params,
        }
        with self.assertRaises(ValueError):
            build_strategies(strategies, AgentEnum.OEM, tc)

    def test_contract_is_leased_with_fee_per_product(self):
        _, oem, _ = self._make("month")
        v = oem.contract_for(ProductEnum.V)
        r = oem.contract_for(ProductEnum.R)
        self.assertEqual(v.kind, ContractKind.LEASED)
        self.assertEqual(v.term_steps, 12)
        self.assertAlmostEqual(v.fee_per_step, 70.0)
        self.assertAlmostEqual(r.fee_per_step, 55.0)

    def test_no_sale_revenue(self):
        _, oem, _ = self._make()
        oem._factory_stock[ProductEnum.V] = 1
        balance_before = oem._balance
        self.assertIsNotNone(oem.request_product(ProductEnum.V))
        self.assertEqual(oem._balance, balance_before)
        self.assertEqual(oem._sale_revenue[ProductEnum.V], 0.0)

    def test_fees_over_a_lease_add_up_at_every_time_unit(self):
        """12 months at EUR 70 = EUR 840, whatever the step length."""
        for unit in ("day", "week", "month"):
            with self.subTest(unit=unit):
                world, oem, customer = self._make(unit)
                customer.become_user(self.rng, ProductEnum.V)
                contract = customer.contract()
                assert contract is not None and contract.term_steps is not None
                term = contract.term_steps
                self.assertEqual(customer.end_of_life_step(), world.now() + term)
                for _ in range(term):
                    world.tick()
                    customer._handle_active_user(self.rng)
                self.assertAlmostEqual(oem._total_contract_fees, 12 * 70.0)
                self.assertIsNone(customer.contract())  # lease ended
                self.assertEqual(len(oem._incoming_cores), 1)  # core always returned

    def test_leased_core_returned_even_with_zero_return_rate(self):
        world, oem, customer = self._make()
        customer._core_return_rate = 0.0
        customer.become_user(self.rng, ProductEnum.V)
        customer._end_of_life_step = world.now()
        customer._handle_active_user(self.rng)
        self.assertEqual(len(oem._incoming_cores), 1)

    def test_leased_core_acceptance_and_collection_cost(self):
        _, oem, _ = self._make()
        leased = oem.contract_for(ProductEnum.V)
        oem._core_acceptance_rate = 0.7
        oem._core_collection_cost = 20.0
        # 0.84 < 0.7 + 0.15 = 0.85, so accepted only thanks to the uplift
        oem.return_product(_MockRNG(0.84), None, leased)
        self.assertEqual(oem._total_cores_rejected, 0)
        self.assertAlmostEqual(oem._total_core_collection_cost, 15.0)

    def test_owned_core_unaffected_by_lease_hooks(self):
        tc = ModelTimeConverter.from_config(self.config)
        lease = Lease(self.params, tc)
        self.assertEqual(lease.acceptance_rate(None, 0.7), 0.7)
        self.assertEqual(lease.collection_cost(None, 20.0), 20.0)
        self.assertEqual(lease.return_probability(None, 0.8), 0.8)

    def test_leases_in_use_and_remaining_fees(self):
        world, oem, customer = self._make("month")
        customer.become_user(self.rng, ProductEnum.V)
        for _ in range(4):  # 4 of 12 months paid
            world.tick()
            customer._handle_active_user(self.rng)
        units, remaining = oem.leases_in_use()
        self.assertEqual(units, 1)
        self.assertAlmostEqual(remaining, 8 * 70.0)
        report = oem.generate_financial_report()
        self.assertAlmostEqual(
            report["Breakdown"]["Sale of lease contracts (fees)"], 4 * 70.0
        )
        self.assertEqual(report["Statistics"]["Units on lease at end"], 1)

    def test_starting_customer_is_a_lessee(self):
        world, _, customer = self._make("month")
        customer.initialise_as_active_user(self.rng, ProductEnum.V)
        contract = customer.contract()
        assert contract is not None
        self.assertEqual(contract.kind, ContractKind.LEASED)
        self.assertLessEqual(customer.end_of_life_step(), world.now() + 12)

    def test_ignored_without_reman(self):
        self.config["main"]["enable_reman"] = False
        _, oem, _ = self._make()
        self.assertEqual(oem.contract_for(ProductEnum.V).kind, ContractKind.OWNED)


if __name__ == "__main__":
    unittest.main()
