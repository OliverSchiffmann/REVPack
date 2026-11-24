import unittest
from reuman.model_time_converter import (
    ModelTimeConverter,
    TimeUnit,
    DAYS_PER_YEAR,
    unit_for_frequency,
)

DAY = ModelTimeConverter(TimeUnit.DAY)
WEEK = ModelTimeConverter(TimeUnit.WEEK)
MONTH = ModelTimeConverter(TimeUnit.MONTH)


class TestModelTimeConverter(unittest.TestCase):

    def test_from_config(self):
        """The converter is built from config["main"]["time_unit"]."""
        conv = ModelTimeConverter.from_config({"main": {"time_unit": "week"}})
        self.assertEqual(conv.unit, TimeUnit.WEEK)

    def test_from_config_rejects_unknown_unit(self):
        """Unsupported units (e.g. Simplan's 'hourly' or 'yearly') give a readable error."""
        for bad in ["hour", "year", "Week", ""]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    ModelTimeConverter.from_config({"main": {"time_unit": bad}})

    def test_calendar_is_consistent(self):
        """Every resolution covers exactly the same number of days in a year."""
        self.assertEqual(DAYS_PER_YEAR, 336)
        for conv, steps in [(DAY, 336), (WEEK, 48), (MONTH, 12)]:
            with self.subTest(unit=conv.unit):
                self.assertEqual(conv.steps_per_year, steps)
                self.assertEqual(
                    conv.steps_per_year * conv.days_per_step, DAYS_PER_YEAR
                )

    def test_years_to_steps(self):
        self.assertEqual(DAY.years_to_steps(5), 1680)
        self.assertEqual(WEEK.years_to_steps(5), 240)
        self.assertEqual(MONTH.years_to_steps(5), 60)

    def test_years_to_steps_rejects_bad_values(self):
        """Simulation length must be a whole number of years >= 1."""
        for bad in [0, -1, 2.5, True]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    WEEK.years_to_steps(bad)

    def test_days_to_steps_under_one_step_is_zero(self):
        """Durations shorter than a step finish within the step."""
        self.assertEqual(WEEK.days_to_steps(3), 0)
        self.assertEqual(WEEK.days_to_steps(6.9), 0)
        self.assertEqual(MONTH.days_to_steps(27), 0)
        self.assertEqual(DAY.days_to_steps(0), 0)

    def test_days_to_steps_rounds_to_nearest(self):
        """Durations of a step or more round to the nearest step, halves up."""
        self.assertEqual(DAY.days_to_steps(5), 5)
        self.assertEqual(WEEK.days_to_steps(7), 1)
        self.assertEqual(WEEK.days_to_steps(10), 1)  # 1.43 weeks
        self.assertEqual(WEEK.days_to_steps(10.5), 2)  # exactly 1.5 weeks rounds up
        self.assertEqual(WEEK.days_to_steps(17.5), 3)  # 2.5 weeks: round() would give 2
        self.assertEqual(MONTH.days_to_steps(500), 18)  # 17.86 months

    def test_days_to_steps_rejects_negative(self):
        """Special values like patience = -1 must be handled by the caller, not converted."""
        with self.assertRaises(ValueError):
            WEEK.days_to_steps(-1)

    def test_daily_prob_to_step_prob(self):
        """Per-step probability is 1 - (1 - p)^days, not days * p."""
        self.assertAlmostEqual(DAY.daily_prob_to_step_prob(0.02), 0.02)
        self.assertAlmostEqual(WEEK.daily_prob_to_step_prob(0.02), 1 - 0.98**7)
        self.assertAlmostEqual(MONTH.daily_prob_to_step_prob(0.02), 1 - 0.98**28)
        self.assertLess(MONTH.daily_prob_to_step_prob(0.02), 28 * 0.02)
        self.assertEqual(MONTH.daily_prob_to_step_prob(0.0), 0.0)
        self.assertEqual(MONTH.daily_prob_to_step_prob(1.0), 1.0)

    def test_daily_prob_rejects_out_of_range(self):
        for bad in [-0.1, 1.1]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    WEEK.daily_prob_to_step_prob(bad)

    def test_frequency_names_match_simplan(self):
        self.assertEqual(DAY.frequency, "daily")
        self.assertEqual(WEEK.frequency, "weekly")
        self.assertEqual(MONTH.frequency, "monthly")

    def test_daily_prob_keeps_full_precision(self):
        """In daily steps the rate must come back unchanged, not 0.00029999999999996696."""
        self.assertEqual(DAY.daily_prob_to_step_prob(0.0003), 0.0003)

    def test_unit_for_frequency(self):
        self.assertEqual(unit_for_frequency("daily"), TimeUnit.DAY)
        self.assertEqual(unit_for_frequency("weekly"), TimeUnit.WEEK)
        self.assertEqual(unit_for_frequency("monthly"), TimeUnit.MONTH)
        for bad in ["hourly", "yearly", "Daily"]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    unit_for_frequency(bad)

    def test_period_prob_same_length_is_unchanged(self):
        """A weekly rate in weekly steps comes back exactly as it went in."""
        self.assertEqual(WEEK.period_prob_to_step_prob(0.0042, TimeUnit.WEEK), 0.0042)

    def test_period_prob_longer_step(self):
        """Weekly rate into monthly steps: 4 weeks per month."""
        self.assertAlmostEqual(
            MONTH.period_prob_to_step_prob(0.1, TimeUnit.WEEK), 1 - 0.9**4
        )

    def test_period_prob_shorter_step(self):
        """Monthly rate into daily steps: the daily rate that compounds to the monthly one."""
        p_day = DAY.period_prob_to_step_prob(0.2, TimeUnit.MONTH)
        self.assertAlmostEqual(1 - (1 - p_day) ** 28, 0.2)

    def test_period_prob_round_trip(self):
        """Daily -> monthly -> daily gets back to where it started."""
        p_month = MONTH.period_prob_to_step_prob(0.0006, TimeUnit.DAY)
        self.assertAlmostEqual(
            DAY.period_prob_to_step_prob(p_month, TimeUnit.MONTH), 0.0006
        )

    def test_daily_amounts_to_step_amounts(self):
        """A list of daily amounts is added up per step; a short last group is kept."""
        self.assertEqual(WEEK.daily_amounts_to_step_amounts([1] * 10), [7, 3])
        self.assertEqual(MONTH.daily_amounts_to_step_amounts([2] * 28), [56])
        self.assertEqual(DAY.daily_amounts_to_step_amounts([4, 5]), [4, 5])

    def test_per_day_and_per_year_conversions_agree(self):
        """€X per day for a year costs the same in total at every resolution."""
        for conv in [DAY, WEEK, MONTH]:
            with self.subTest(unit=conv.unit):
                self.assertAlmostEqual(
                    conv.per_day_to_per_step(2.0) * conv.steps_per_year,
                    2.0 * DAYS_PER_YEAR,
                )
                self.assertAlmostEqual(
                    conv.per_year_to_per_step(5000.0) * conv.steps_per_year, 5000.0
                )

    def test_step_to_day(self):
        self.assertEqual(DAY.step_to_day(10), 10)
        self.assertEqual(WEEK.step_to_day(10), 70)
        self.assertEqual(MONTH.step_to_day(12), DAYS_PER_YEAR)

    def test_converter_cannot_be_changed(self):
        """The unit is fixed for a whole run."""
        with self.assertRaises(AttributeError):
            WEEK.unit = TimeUnit.DAY  # type: ignore


if __name__ == "__main__":
    unittest.main()
