import asyncio
import copy
import unittest
from examples.simulation_runner import run_simulation
from tests.test_scenarios import TEST_SCENARIOS


class TestSimulationRunner(unittest.TestCase):
    """End-to-end smoke tests: the runner reads a scenario and completes a run."""

    def setUp(self):
        self.config = copy.deepcopy(TEST_SCENARIOS["Default"])
        self.config["main"]["B2B_population"] = 50  # small, so the test is fast
        self.config["main"]["simulation_years"] = 1

    def test_runs_for_the_configured_number_of_years(self):
        results, report = asyncio.run(run_simulation(self.config))
        self.assertEqual(len(results["step"]), 336)  # 1 model year of days
        self.assertEqual(results["day"][-1], 336)
        self.assertIn("Total Cost", report)

    def test_runs_at_every_time_unit(self):
        """One year is 336 days whatever the step length."""
        for unit, n_steps in [("day", 336), ("week", 48), ("month", 12)]:
            with self.subTest(unit=unit):
                self.config["main"]["time_unit"] = unit
                results, _ = asyncio.run(run_simulation(self.config))
                self.assertEqual(len(results["step"]), n_steps)
                self.assertEqual(results["day"][-1], 336)


if __name__ == "__main__":
    unittest.main()
