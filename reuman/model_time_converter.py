"""
Converts real-world time units into model time steps.

The model always advances one step at a time. A step can be a day, a week or
a month. Scenario parameters are always given in real-world units (days, per
day, per year), and are converted to steps here, once, before the simulation
starts. All unit maths lives in this module and nowhere else.

Calendar used by the model (deliberately simple, see DAYS_PER_STEP):
    1 week = 7 days, 1 month = 4 weeks = 28 days, 1 year = 12 months = 336 days
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from enum import Enum

DAYS_PER_WEEK = 7
WEEKS_PER_MONTH = 4
MONTHS_PER_YEAR = 12
DAYS_PER_YEAR = DAYS_PER_WEEK * WEEKS_PER_MONTH * MONTHS_PER_YEAR  # 336


class TimeUnit(str, Enum):
    """The length of one model step."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"


DAYS_PER_STEP = {
    TimeUnit.DAY: 1,
    TimeUnit.WEEK: DAYS_PER_WEEK,
    TimeUnit.MONTH: DAYS_PER_WEEK * WEEKS_PER_MONTH,
}


@dataclass(frozen=True)
class ModelTimeConverter:
    """
    Converts real-world durations, rates and costs into per-step values for one time unit.

    Create one per simulation (from the scenario config) and use it everywhere a
    parameter given in days or years needs to become a number of steps.
    """

    unit: TimeUnit

    @classmethod
    def from_config(cls, config: dict) -> ModelTimeConverter:
        """
        Build a converter from a scenario config.

        Args:
            config (dict): Full scenario config; reads config["main"]["time_unit"].

        Raises:
            ValueError: If time_unit is not "day", "week" or "month".
        """
        value = config["main"]["time_unit"]
        try:
            unit = TimeUnit(value)
        except ValueError:
            allowed = ", ".join(f'"{u.value}"' for u in TimeUnit)
            raise ValueError(
                f"time_unit must be one of {allowed}. Received: {value!r}"
            ) from None
        return cls(unit)

    @property
    def days_per_step(self) -> int:
        """Number of model days in one step (1, 7 or 28)."""
        return DAYS_PER_STEP[self.unit]

    @property
    def steps_per_year(self) -> int:
        """Number of steps in one model year (336, 48 or 12)."""
        return DAYS_PER_YEAR // self.days_per_step

    def years_to_steps(self, years: int) -> int:
        """
        Convert a simulation length in whole years into a number of steps.

        Raises:
            ValueError: If years is not a positive whole number.
        """
        if isinstance(years, bool) or not isinstance(years, int) or years < 1:
            raise ValueError(
                f"Simulation length must be a whole number of years >= 1. Received: {years!r}"
            )
        return years * self.steps_per_year

    def days_to_steps(self, days: float) -> int:
        """
        Convert a duration in days into a whole number of steps.

        Rule: anything shorter than one step takes 0 steps (it finishes within
        the step). Anything longer is rounded to the nearest step, halves up.

        Callers must handle special values (e.g. patience = -1 meaning
        "infinite") before calling this; negative durations are rejected.

        Raises:
            ValueError: If days is negative.
        """
        if days < 0:
            raise ValueError(f"A duration cannot be negative. Received: {days} days")
        steps = days / self.days_per_step
        if steps < 1:
            return 0
        # Not round(): Python rounds halves to the nearest EVEN number (round(2.5) == 2)
        return math.floor(steps + 0.5)

    def daily_prob_to_step_prob(self, p_daily: float) -> float:
        """
        Convert a probability per day into the probability of it happening at least once in a step.

        Uses 1 - (1 - p)^n

        Raises:
            ValueError: If p_daily is not between 0 and 1.
        """
        if not 0.0 <= p_daily <= 1.0:
            raise ValueError(
                f"A probability must be between 0 and 1. Received: {p_daily}"
            )
        return 1.0 - (1.0 - p_daily) ** self.days_per_step

    def per_day_to_per_step(self, value_per_day: float) -> float:
        """Convert an amount per day (e.g. € per core per day, units per day) into an amount per step."""
        return value_per_day * self.days_per_step

    def per_year_to_per_step(self, value_per_year: float) -> float:
        """Convert an amount per year (e.g. € per year) into an amount per step."""
        return value_per_year / self.steps_per_year

    def step_to_day(self, step: int) -> int:
        """Model day on which a step ends, for plotting results on a common day axis."""
        return step * self.days_per_step
