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


# Strategy name (as used in the config) -> class.
STRATEGY_REGISTRY: dict[str, type[CollectionStrategy]] = {
    BuyBack.name: BuyBack,
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
