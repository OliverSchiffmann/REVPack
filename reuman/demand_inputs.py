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

EXPECTED_RESULT_TYPE = "timeseries.forecast"
EXPECTED_FREQUENCY = "daily"
EXPECTED_AGGREGATION = "sum"

# The fields each row of each table must have
REQUIRED_FIELDS = {
    "input": ("date", "y"),  # real (historic) data
    "forecast": ("date", "yhat"),  # Prophet's fitted values and forecast
}


class ForecastFormatError(ValueError):
    """Raised when a forecast is not in the expected Simplan format."""


class DailySeries(NamedTuple):
    """One value per day: real data first, then forecast."""

    dates: list[date]
    values: list[float]
    history_days: int  # how many of the values are real data
    clipped_days: int  # how many negative forecast values were set to 0


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
        data (dict): A parsed Simplan forecast.
    """
    if not isinstance(data, dict):
        raise ForecastFormatError("Forecast must be a JSON object.")

    result_type = data.get("resultType")
    if result_type != EXPECTED_RESULT_TYPE:
        raise ForecastFormatError(
            f"Expected resultType '{EXPECTED_RESULT_TYPE}', got '{result_type}'."
        )

    params = data.get("parameters", {})
    if params.get("frequency") != EXPECTED_FREQUENCY:
        raise ForecastFormatError(
            f"Forecast must be daily, got frequency '{params.get('frequency')}'."
        )
    if params.get("aggregation") != EXPECTED_AGGREGATION:
        raise ForecastFormatError(
            "Forecast values must be daily totals (aggregation 'sum'), "
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


def build_daily_series(data: dict) -> DailySeries:
    """
    Join a forecast's real history and its future forecast into one daily series.

    Real values ('input' table, field 'y') are used for every day they exist.
    Forecast values ('forecast' table, field 'yhat') are used only for the days
    after the history ends. Negative forecast values are set to 0.

    Args:
        data (dict): A parsed, validated Simplan forecast.

    Returns:
        DailySeries: The joined series.
    """
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

    # Every day must follow the previous one exactly: no gaps, no repeats
    for previous, current in zip(dates, dates[1:]):
        if current - previous != timedelta(days=1):
            raise ForecastFormatError(
                f"Dates are not consecutive days: {previous} is followed by {current}."
            )

    if any(v < 0 for v in hist_values):
        raise ForecastFormatError("The real (input) data contains negative values.")

    return DailySeries(dates, values, len(hist_values), clipped)


def round_sig(x: float, sig: int = 4) -> float:
    """Round x to `sig` significant figures (e.g. 0.000308712 -> 0.0003087)."""
    if x == 0:
        return 0.0
    return round(x, sig - 1 - math.floor(math.log10(abs(x))))


def estimate_ad_rates(
    series_v: DailySeries | None,
    series_r: DailySeries | None,
    market_size: int,
    starting_customers: int = 0,
) -> dict[str, float]:
    """
    Estimate a constant daily advertising rate for each product from its series.

    Rate = total new customers / total customer-days in the pool, where the pool
    on each day is the market size, minus starting customers, minus everyone
    who became a V or R customer on an earlier day (both products share one pool).

    Args:
        series_v: Daily series for virgin products, or None.
        series_r: Daily series for reman products, or None.
        market_size (int): Total possible customers (N).
        starting_customers (int): Customers who already own the product on day 1 (S).

    Returns:
        dict: {"V": rate, "R": rate} for each product that had a series,
        rounded to 4 significant figures.
    """
    given = {k: s for k, s in (("V", series_v), ("R", series_r)) if s is not None}
    if not given:
        raise ValueError("At least one forecast series is needed.")

    # Both series must cover the same days, otherwise the shared pool is undefined
    date_ranges = {k: (s.dates[0], s.dates[-1]) for k, s in given.items()}
    if len(set(date_ranges.values())) > 1:
        raise ForecastFormatError(
            f"V and R forecasts must cover the same dates, got {date_ranges}."
        )

    n_days = len(next(iter(given.values())).values)
    pool = market_size - starting_customers
    pool_days = 0.0  # sum of the pool size over all days

    for t in range(n_days):
        if pool <= 0:
            raise ValueError(
                f"The market runs out of potential customers on day {t + 1}. "
                "Market size is too small for these sales figures."
            )
        pool_days += pool
        pool -= sum(s.values[t] for s in given.values())

    return {k: round_sig(sum(s.values) / pool_days) for k, s in given.items()}
