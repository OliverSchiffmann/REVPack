import copy
import json
import os
import tempfile
import unittest
from datetime import date, timedelta

import numpy as np

from reuman import demand_inputs
from reuman.demand_inputs import (
    DailySeries,
    ForecastFormatError,
    build_daily_series,
    estimate_ad_rates,
    load_forecast_file,
    round_sig,
    validate_forecast,
)

START = date(2025, 1, 1)


def make_forecast(history, future=(), start=START):
    """
    Build a minimal Simplan-style forecast dict.

    history: real daily values (the 'input' table).
    future: forecast values for the days after the history.
    The 'forecast' table covers history + future days, like Simplan's output,
    with yhat set to 999 on history days so tests can tell if it is wrongly used.
    """
    days = [start + timedelta(days=i) for i in range(len(history) + len(future))]
    stamp = lambda d: d.isoformat() + "T00:00:00Z"
    return {
        "resultType": "timeseries.forecast",
        "parameters": {"frequency": "daily", "aggregation": "sum"},
        "tables": {
            "input": [{"date": stamp(d), "y": y} for d, y in zip(days, history)],
            "forecast": [
                {"date": stamp(d), "yhat": 999.0} for d in days[: len(history)]
            ]
            + [
                {"date": stamp(d), "yhat": y}
                for d, y in zip(days[len(history) :], future)
            ],
        },
    }


def make_series(values, start=START):
    """Build a DailySeries directly, for tests of estimate_ad_rates."""
    days = [start + timedelta(days=i) for i in range(len(values))]
    return DailySeries(days, list(values), len(values), 0)


class TestValidateForecast(unittest.TestCase):

    def setUp(self):
        self.good = make_forecast([1, 2, 3], [4, 5])

    def test_accepts_valid_forecast(self):
        validate_forecast(self.good)  # should not raise

    def test_rejects_wrong_result_type(self):
        bad = copy.deepcopy(self.good)
        bad["resultType"] = "something.else"
        with self.assertRaises(ForecastFormatError):
            validate_forecast(bad)

    def test_rejects_non_daily_frequency(self):
        bad = copy.deepcopy(self.good)
        bad["parameters"]["frequency"] = "weekly"
        with self.assertRaises(ForecastFormatError):
            validate_forecast(bad)

    def test_rejects_non_sum_aggregation(self):
        bad = copy.deepcopy(self.good)
        bad["parameters"]["aggregation"] = "mean"
        with self.assertRaises(ForecastFormatError):
            validate_forecast(bad)

    def test_rejects_missing_table(self):
        bad = copy.deepcopy(self.good)
        del bad["tables"]["input"]
        with self.assertRaises(ForecastFormatError):
            validate_forecast(bad)

    def test_rejects_row_missing_field(self):
        bad = copy.deepcopy(self.good)
        del bad["tables"]["forecast"][2]["yhat"]
        with self.assertRaises(ForecastFormatError):
            validate_forecast(bad)

    def test_rejects_non_dict(self):
        with self.assertRaises(ForecastFormatError):
            validate_forecast([1, 2, 3])

    def test_load_forecast_file_reads_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "forecast.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.good, f)
            self.assertEqual(load_forecast_file(path), self.good)


class TestBuildDailySeries(unittest.TestCase):

    def test_uses_real_history_then_forecast(self):
        s = build_daily_series(make_forecast([1, 2, 3], [4, 5]))
        # 999 would mean yhat was used on a history day
        self.assertEqual(s.values, [1, 2, 3, 4, 5])
        self.assertEqual(s.history_days, 3)
        self.assertEqual(s.dates[0], START)
        self.assertEqual(s.dates[-1], START + timedelta(days=4))

    def test_clips_negative_forecast_values(self):
        s = build_daily_series(make_forecast([1, 2], [-3, 4]))
        self.assertEqual(s.values, [1, 2, 0.0, 4])
        self.assertEqual(s.clipped_days, 1)

    def test_rejects_negative_history(self):
        with self.assertRaises(ForecastFormatError):
            build_daily_series(make_forecast([1, -2, 3]))

    def test_rejects_gap_in_dates(self):
        data = make_forecast([1, 2, 3, 4])
        del data["tables"]["input"][2]  # remove one day
        with self.assertRaises(ForecastFormatError):
            build_daily_series(data)

    def test_sorts_rows_that_are_out_of_order(self):
        data = make_forecast([1, 2, 3])
        data["tables"]["input"].reverse()
        self.assertEqual(build_daily_series(data).values, [1, 2, 3])


class TestRoundSig(unittest.TestCase):

    def test_rounds_to_four_significant_figures(self):
        self.assertEqual(round_sig(0.000308712), 0.0003087)
        self.assertEqual(round_sig(123456.0), 123500.0)
        self.assertEqual(round_sig(2.0 / 19.0), 0.1053)

    def test_zero(self):
        self.assertEqual(round_sig(0.0), 0.0)


class TestEstimateAdRates(unittest.TestCase):

    def test_hand_calculation(self):
        # Pool 10 on day 1, 9 on day 2: rate = 2 / (10 + 9)
        rates = estimate_ad_rates(make_series([1, 1]), None, market_size=10)
        self.assertEqual(rates, {"V": round_sig(2 / 19)})

    def test_starting_customers_reduce_the_pool(self):
        # Pool 8 then 7: rate = 2 / 15
        rates = estimate_ad_rates(
            make_series([1, 1]), None, market_size=10, starting_customers=2
        )
        self.assertEqual(rates["V"], round_sig(2 / 15))

    def test_recovers_known_rates(self):
        # Generate sales the same way the model does, then check the
        # estimator finds the rates it was generated with
        rng = np.random.default_rng(0)
        N, S, p_v, p_r = 1_000_000, 1000, 3e-4, 1e-5
        pool, v, r = N - S, [], []
        for _ in range(500):
            a = rng.binomial(pool, p_v)
            pool -= a
            b = rng.binomial(pool, p_r)
            pool -= b
            v.append(a)
            r.append(b)
        rates = estimate_ad_rates(make_series(v), make_series(r), N, S)
        # ~150,000 V and ~5,000 R events, so random error is ~0.3% and ~1.4%
        self.assertAlmostEqual(rates["V"] / p_v, 1.0, delta=0.02)
        self.assertAlmostEqual(rates["R"] / p_r, 1.0, delta=0.05)

    def test_reman_sales_shrink_the_shared_pool(self):
        v, r = make_series([100] * 50), make_series([100] * 50)
        alone = estimate_ad_rates(v, None, market_size=20_000)["V"]
        shared = estimate_ad_rates(v, r, market_size=20_000)["V"]
        # A smaller pool means each potential customer was more likely to buy
        self.assertGreater(shared, alone)

    def test_reman_only(self):
        rates = estimate_ad_rates(None, make_series([1, 1]), market_size=10)
        self.assertEqual(set(rates), {"R"})

    def test_rejects_no_series(self):
        with self.assertRaises(ValueError):
            estimate_ad_rates(None, None, market_size=10)

    def test_rejects_mismatched_dates(self):
        v = make_series([1, 1])
        r = make_series([1, 1], start=START + timedelta(days=1))
        with self.assertRaises(ForecastFormatError):
            estimate_ad_rates(v, r, market_size=100)

    def test_rejects_market_that_runs_out(self):
        # Day 1 uses 6 of 10, so day 2's 6 sales exceed the 4 left
        with self.assertRaises(ValueError):
            estimate_ad_rates(make_series([6, 6]), None, market_size=10)

    def test_rejects_empty_pool(self):
        with self.assertRaises(ValueError):
            estimate_ad_rates(
                make_series([0, 0]), None, market_size=10, starting_customers=10
            )


if __name__ == "__main__":
    unittest.main()
