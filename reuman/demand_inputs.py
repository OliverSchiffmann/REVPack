"""
Turns external demand data (for example Simplan forecast files) into
demand_profile parameters for the simulation.

Everything here runs once, before the simulation starts. Nothing here
simulates anything.
"""

from __future__ import annotations
import json
from datetime import date, timedelta
from typing import NamedTuple
import math
from .model_time_converter import FREQUENCY_NAMES

EXPECTED_RESULT_TYPE = "timeseries.forecast"
EXPECTED_AGGREGATION = "sum"
ALLOWED_FREQUENCIES = tuple(FREQUENCY_NAMES.values())  # "daily", "weekly", "monthly"
# The fields each row of each table must have
REQUIRED_FIELDS = {
    "input": ("date", "y"),  # real (historic) data
    "forecast": ("date", "yhat"),  # Prophet's fitted values and forecast
}


class ForecastFormatError(ValueError):
    """Raised when a forecast is not in the expected Simplan format."""


class ForecastSeries(NamedTuple):
    """One value per period (day, week or month): real data first, then forecast."""

    dates: list[date]
    values: list[float]
    history_periods: int  # how many of the values are real data
    clipped_periods: int  # how many negative forecast values were set to 0
    frequency: str = "daily"  # "daily", "weekly" or "monthly", from the forecast file


def load_forecast_file(path: str) -> dict:
    """
    Read a Simplan forecast JSON file from disk and check its format.

    Only used when running from Python scripts. The webapp reads the file in
    the browser and passes the parsed data straight to validate_forecast().

    Args:
        path (str): Path to the forecast .json file.

    Returns:
        dict: The parsed forecast.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    validate_forecast(data)
    return data


def validate_forecast(data: dict) -> None:
    """
    Check that a parsed forecast has the structure this module relies on.

    Raises ForecastFormatError with a readable message if it does not.
    Returns nothing if the forecast is fine.

    Args:
        data (dict): A parsed Simplan forecast. Its frequency can be "daily",
            "weekly" or "monthly", independent of the model's time step.
    """
    if not isinstance(data, dict):
        raise ForecastFormatError("Forecast must be a JSON object.")

    result_type = data.get("resultType")
    if result_type != EXPECTED_RESULT_TYPE:
        raise ForecastFormatError(
            f"Expected resultType '{EXPECTED_RESULT_TYPE}', got '{result_type}'."
        )

    params = data.get("parameters", {})
    if params.get("frequency") not in ALLOWED_FREQUENCIES:
        raise ForecastFormatError(
            f"Forecast frequency must be one of {', '.join(ALLOWED_FREQUENCIES)}, "
            f"got '{params.get('frequency')}'."
        )
    if params.get("aggregation") != EXPECTED_AGGREGATION:
        raise ForecastFormatError(
            "Forecast values must be totals per period (aggregation 'sum'), "
            f"got '{params.get('aggregation')}'."
        )

    tables = data.get("tables", {})
    for table_name, fields in REQUIRED_FIELDS.items():
        rows = tables.get(table_name)
        if not rows:
            raise ForecastFormatError(f"Forecast has no '{table_name}' table.")
        for i, row in enumerate(rows):
            missing = [f for f in fields if f not in row]
            if missing:
                raise ForecastFormatError(
                    f"Row {i} of the '{table_name}' table is missing {missing}."
                )


def _parse_date(text: str) -> date:
    """Turn '2025-01-06T00:00:00Z' into a date. Only the day matters."""
    return date.fromisoformat(text[:10])


def _is_next_period(previous: date, current: date, frequency: str) -> bool:
    """True if `current` is the period straight after `previous` at this frequency."""
    if frequency == "daily":
        return current - previous == timedelta(days=1)
    if frequency == "weekly":
        return current - previous == timedelta(days=7)
    # Monthly: Simplan labels each calendar month by a date in it, so compare months
    months = lambda d: d.year * 12 + d.month
    return months(current) - months(previous) == 1


def build_forecast_series(data: dict) -> ForecastSeries:
    """
    Join a forecast's real history and its future forecast into one series,
    with one value per period (day, week or month).

    Real values ('input' table, field 'y') are used for every period they exist.
    Forecast values ('forecast' table, field 'yhat') are used only for the periods
    after the history ends. Negative forecast values are set to 0.

    Args:
        data (dict): A parsed, validated Simplan forecast. The frequency is read
            from the forecast itself and stored in the returned series.
    Returns:
        ForecastSeries: The joined series.
    """
    frequency = data["parameters"]["frequency"]
    history = sorted(data["tables"]["input"], key=lambda r: r["date"])
    hist_dates = [_parse_date(r["date"]) for r in history]
    hist_values = [float(r["y"]) for r in history]
    last_history_day = hist_dates[-1]

    future = [
        r
        for r in data["tables"]["forecast"]
        if _parse_date(r["date"]) > last_history_day
    ]
    future.sort(key=lambda r: r["date"])
    fut_dates = [_parse_date(r["date"]) for r in future]
    raw_future = [float(r["yhat"]) for r in future]
    fut_values = [max(0.0, v) for v in raw_future]
    clipped = sum(1 for v in raw_future if v < 0)

    dates = hist_dates + fut_dates
    values = hist_values + fut_values

    # Every period must follow the previous one exactly: no gaps, no repeats
    for previous, current in zip(dates, dates[1:]):
        if not _is_next_period(previous, current, frequency):
            raise ForecastFormatError(
                f"Dates are not consecutive {frequency} periods: "
                f"{previous} is followed by {current}."
            )

    if any(v < 0 for v in hist_values):
        raise ForecastFormatError("The real (input) data contains negative values.")

    return ForecastSeries(dates, values, len(hist_values), clipped, frequency)


def round_sig(x: float, sig: int = 4) -> float:
    """Round x to `sig` significant figures (e.g. 0.000308712 -> 0.0003087)."""
    if x == 0:
        return 0.0
    return round(x, sig - 1 - math.floor(math.log10(abs(x))))


def estimate_ad_rates(
    series_v: ForecastSeries | None,
    series_r: ForecastSeries | None,
    market_size: int,
    starting_customers: int = 0,
) -> dict[str, float]:
    """
    Estimate a constant advertising rate per period (per day, week or month,
    matching the series' frequency) for each product from its series.

    Rate = total new customers / total customer-periods in the pool, where the pool
    in each period is the market size, minus starting customers, minus everyone
    who became a V or R customer in an earlier period (both products share one pool).

    Args:
        series_v: Forecast series for virgin products, or None.
        series_r: Forecast series for reman products, or None.
        market_size (int): Total possible customers (N).
        starting_customers (int): Customers who already own the product on day 1 (S).

    Returns:
        dict: {"V": rate, "R": rate} for each product that had a series,
        rounded to 4 significant figures.
    """
    given = {k: s for k, s in (("V", series_v), ("R", series_r)) if s is not None}
    if not given:
        raise ValueError("At least one forecast series is needed.")

    # Both series must have the same frequency and cover the same dates,
    # otherwise the shared pool is undefined
    frequencies = {k: s.frequency for k, s in given.items()}
    if len(set(frequencies.values())) > 1:
        raise ForecastFormatError(
            f"V and R forecasts must have the same frequency, got {frequencies}."
        )
    # Both series must cover the same days, otherwise the shared pool is undefined
    date_ranges = {k: (s.dates[0], s.dates[-1]) for k, s in given.items()}
    if len(set(date_ranges.values())) > 1:
        raise ForecastFormatError(
            f"V and R forecasts must cover the same dates, got {date_ranges}."
        )

    n_days = len(next(iter(given.values())).values)
    pool = market_size - starting_customers
    if pool <= 0:
        raise ValueError(
            "There are no potential customers: starting customers must be "
            "fewer than the market size."
        )
    pool_days = 0.0  # sum of the pool size over all days

    for t in range(n_days):
        day_sales = sum(s.values[t] for s in given.values())
        if day_sales > pool:
            raise ValueError(
                f"On day {t + 1} the data has {day_sales:g} new customers but only "
                f"{pool:g} potential customers are left. "
                "Market size is too small for these sales figures."
            )
        pool_days += pool
        pool -= day_sales

    return {k: round_sig(sum(s.values) / pool_days) for k, s in given.items()}
