"""
Core collection strategies (T5.3): contract and incentive schemes that change how
many cores come back, in what condition, and at what cost.

Each strategy is a small class that overrides only the hooks it needs. The actor
that runs the collection (the OEM for now, a third-party remanufacturer later)
holds a list of strategies and passes each value through them in turn, starting
from its own base value. With no strategies, every hook returns the base value
unchanged, so the model behaves exactly as it did before strategies existed.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, Protocol
from ._agent import AgentEnum
from .product import ProductEnum

if TYPE_CHECKING:
    from .model_time_converter import ModelTimeConverter


class ContractKind(str, Enum):
    """How the customer holds the product."""

    OWNED = "owned"  # bought outright (current behaviour)
    LEASED = "leased"  # operator keeps ownership, customer pays a fee per step


class ContractOperator(Protocol):
    """
    What a customer needs from the agent it holds a contract with. Any agent with
    these methods can be an operator (the OEM now, a third-party remanufacturer later).
    """

    def receive_contract_fee(self, amount: float) -> None: ...

    def core_return_probability(
        self, contract: Contract | None, base_probability: float
    ) -> float: ...

    def schedule_core_return(
        self, customer_location: str | None = None, contract: Contract | None = None
    ) -> None: ...

    def record_core_not_collected(self) -> None: ...


@dataclass(frozen=True)
class Contract:
    """
    The terms a customer gets a product on. Made by the operator at acquisition and
    kept by the customer until end of life; it travels with the returned core.

    Attributes:
        kind (ContractKind): Owned or leased.
        operator (ContractOperator): The agent the customer pays and returns the core to.
        product (ProductEnum): The product the contract is for.
        term_steps (int | None): Fixed use period in steps, or None to use the drawn lifetime.
        fee_per_step (float): Amount paid to the operator each step of use (0 if owned).
    """

    kind: ContractKind
    operator: ContractOperator
    product: ProductEnum
    term_steps: int | None = None
    fee_per_step: float = 0.0


class CollectionStrategy:
    """
    Base class for a core collection strategy. Every hook returns its input
    unchanged, so a subclass only overrides what it changes.

    Class attributes:
        name: Key used in the config, e.g. "lease".
        allowed_operators: Agent types that may run this strategy.
        incompatible_with: Names of strategies that cannot be enabled at the same time.
        required_params: Config keys the strategy needs besides "enabled".
    Every strategy can also have a one-off "setup_cost" (EUR, default 0): legal,
    IT, training and launch marketing (T5.3 cost structure). The operator pays it
    once at the start.
    """

    name: ClassVar[str] = ""
    allowed_operators: ClassVar[frozenset[AgentEnum]] = frozenset({AgentEnum.OEM})
    incompatible_with: ClassVar[frozenset[str]] = frozenset()
    required_params: ClassVar[tuple[str, ...]] = ()

    def __init__(self, params: dict, time_converter: ModelTimeConverter) -> None:
        missing = [key for key in self.required_params if key not in params]
        if missing:
            raise ValueError(
                f"Collection strategy '{self.name}' is missing: {', '.join(missing)}."
            )
        self._params = params
        self._time_converter = time_converter
        self.setup_cost = float(params.get("setup_cost", 0.0))
        if self.setup_cost < 0:
            raise ValueError(
                f"Collection strategy '{self.name}' setup_cost must be >= 0. "
                f"Received: {self.setup_cost}"
            )

    def offer_contract(self, contract: Contract) -> Contract:
        """Terms offered for a new acquisition (e.g. a lease replaces OWNED)."""
        return contract

    def sale_revenue(self, contract: Contract, revenue: float) -> float:
        """Revenue the operator gets at the moment of acquisition."""
        return revenue

    def return_probability(
        self, contract: Contract | None, probability: float
    ) -> float:
        """Probability that the core comes back at end of life."""
        return probability

    def acceptance_rate(self, contract: Contract | None, rate: float) -> float:
        """Probability that a returned core passes inspection."""
        return rate

    def collection_cost(self, contract: Contract | None, cost: float) -> float:
        """Cost of collecting one core."""
        return cost

    def acquisition_cost(self, contract: Contract | None, cost: float) -> float:
        """Amount paid to the customer for a core that passes inspection."""
        return cost


def _is_owned(contract: Contract | None) -> bool:
    """True if the customer owned the product (None is treated as owned)."""
    return contract is None or contract.kind == ContractKind.OWNED


def _is_leased(contract: Contract | None) -> bool:
    """True if the product was leased."""
    return contract is not None and contract.kind == ContractKind.LEASED


class BuyBack(CollectionStrategy):
    """
    Buy-back (T5.3 strategy 7): the operator pays a fixed amount for each core from
    an owned product that passes inspection. The payment makes owners more likely
    to return their core.

    Params:
        bounty_value (float): Amount paid per accepted core (EUR).
        return_rate_uplift (float): Added to the owner's base return rate
            (0 to 1; the result is capped at 1).
    """

    name = "buy_back"
    incompatible_with = frozenset({"lease"})  # a lessee doesn't own the core to sell
    required_params = ("bounty_value", "return_rate_uplift")

    def __init__(self, params: dict, time_converter: ModelTimeConverter) -> None:
        super().__init__(params, time_converter)
        self._bounty_value = float(params["bounty_value"])
        self._return_rate_uplift = float(params["return_rate_uplift"])
        if self._bounty_value < 0:
            raise ValueError(
                f"buy_back bounty_value must be >= 0. Received: {self._bounty_value}"
            )
        if not 0 <= self._return_rate_uplift <= 1:
            raise ValueError(
                "buy_back return_rate_uplift must be between 0 and 1. "
                f"Received: {self._return_rate_uplift}"
            )

    def return_probability(
        self, contract: Contract | None, probability: float
    ) -> float:
        if not _is_owned(contract):
            return probability
        return min(1.0, probability + self._return_rate_uplift)

    def acquisition_cost(self, contract: Contract | None, cost: float) -> float:
        if not _is_owned(contract):
            return cost
        return cost + self._bounty_value


class Lease(CollectionStrategy):
    """
    Leasing (T5.3 strategy 4, scenario S1): every customer leases instead of buying.
    The operator keeps ownership, the customer pays a monthly fee, and the product
    comes back at the end of a fixed lease period. Planned returns improve core
    quality and make collection cheaper.

    Simplifications: the lease period replaces the drawn lifetime (in-lease failures
    are assumed covered by the fee), every leased core comes back, and a lessee
    takes a new lease when the old one ends.

    Params:
        lease_period (float): Lease length in model months (28 days), at least 1.
        monthly_fee_V (float): Fee per month for a virgin product (EUR).
        monthly_fee_R (float): Fee per month for a reman product (EUR).
        acceptance_uplift (float): Added to the core acceptance rate for leased
            cores (0 to 1; the result is capped at 1).
        collection_cost_saving (float): Share of the core collection cost saved
            for leased cores (0 to 1).
    """

    name = "lease"
    incompatible_with = frozenset({"buy_back"})  # nothing for the lessee to sell
    required_params = (
        "lease_period",
        "monthly_fee_V",
        "monthly_fee_R",
        "acceptance_uplift",
        "collection_cost_saving",
    )

    def __init__(self, params: dict, time_converter: ModelTimeConverter) -> None:
        super().__init__(params, time_converter)
        lease_period = float(params["lease_period"])
        fees = {
            ProductEnum.V: float(params["monthly_fee_V"]),
            ProductEnum.R: float(params["monthly_fee_R"]),
        }
        self._acceptance_uplift = float(params["acceptance_uplift"])
        self._collection_cost_saving = float(params["collection_cost_saving"])
        if lease_period < 1:
            raise ValueError(
                f"lease lease_period must be at least 1 month. Received: {lease_period}"
            )
        if any(fee < 0 for fee in fees.values()):
            raise ValueError(f"lease monthly fees must be >= 0. Received: {fees}")
        for key in ("acceptance_uplift", "collection_cost_saving"):
            if not 0 <= float(params[key]) <= 1:
                raise ValueError(
                    f"lease {key} must be between 0 and 1. Received: {params[key]}"
                )

        # Converted to steps once, here, like every other duration in the model
        self._term_steps = max(1, time_converter.months_to_steps(lease_period))
        self._fee_per_step = {
            product: time_converter.per_month_to_per_step(fee)
            for product, fee in fees.items()
        }

    def offer_contract(self, contract: Contract) -> Contract:
        return Contract(
            kind=ContractKind.LEASED,
            operator=contract.operator,
            product=contract.product,
            term_steps=self._term_steps,
            fee_per_step=self._fee_per_step[contract.product],
        )

    def sale_revenue(self, contract: Contract, revenue: float) -> float:
        # The operator keeps ownership: no sale price, income comes as fees
        return 0.0 if _is_leased(contract) else revenue

    def return_probability(
        self, contract: Contract | None, probability: float
    ) -> float:
        # A leased product always goes back to its owner
        return 1.0 if _is_leased(contract) else probability

    def acceptance_rate(self, contract: Contract | None, rate: float) -> float:
        if not _is_leased(contract):
            return rate
        return min(1.0, rate + self._acceptance_uplift)

    def collection_cost(self, contract: Contract | None, cost: float) -> float:
        if not _is_leased(contract):
            return cost
        return cost * (1.0 - self._collection_cost_saving)


# Strategy name (as used in the config) -> class.
STRATEGY_REGISTRY: dict[str, type[CollectionStrategy]] = {
    BuyBack.name: BuyBack,
    Lease.name: Lease,
}


def build_strategies(
    strategies_config: dict,
    operator_type: AgentEnum,
    time_converter: ModelTimeConverter,
) -> list[CollectionStrategy]:
    """
    Create the enabled strategies for one operator and check they can run together.

    Args:
        strategies_config (dict): The operator's "collection_strategies" block,
            e.g. {"lease": {"enabled": True, ...}}.
        operator_type (AgentEnum): The type of agent running the strategies.
        time_converter (ModelTimeConverter): Converts real-world units to steps.

    Returns:
        list[CollectionStrategy]: The enabled strategies, in config order.

    Raises:
        ValueError: For an unknown strategy name, a strategy this operator type
            cannot run, or two enabled strategies that are incompatible.
    """
    strategies: list[CollectionStrategy] = []
    for name, params in strategies_config.items():
        if name not in STRATEGY_REGISTRY:
            known = ", ".join(sorted(STRATEGY_REGISTRY)) or "none yet"
            raise ValueError(
                f"Unknown collection strategy '{name}'. Known strategies: {known}."
            )
        if not params.get("enabled", False):
            continue
        cls = STRATEGY_REGISTRY[name]
        if operator_type not in cls.allowed_operators:
            raise ValueError(
                f"Collection strategy '{name}' cannot be run by a {operator_type.value}."
            )
        strategies.append(cls(params, time_converter))

    enabled = {s.name for s in strategies}
    for s in strategies:
        clashes = s.incompatible_with & enabled
        if clashes:
            raise ValueError(
                f"Collection strategy '{s.name}' cannot be combined with: "
                f"{', '.join(sorted(clashes))}."
            )
    return strategies
