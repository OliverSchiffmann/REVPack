import unittest, copy
import numpy as np
from reuman._agent import AgentEnum
from reuman.collection_strategies import (
    STRATEGY_REGISTRY,
    BuyBack,
    CollectionStrategy,
    Contract,
    ContractKind,
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
        self.assertIsNotNone(contract)
        self.assertEqual(contract.product, ProductEnum.V)  # type: ignore
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


if __name__ == "__main__":
    unittest.main()
