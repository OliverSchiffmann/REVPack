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

    def test_unsupported_time_unit_is_rejected(self):
        """Until delays, rates and costs are converted, only daily steps may run."""
        self.config["main"]["time_unit"] = "week"
        with self.assertRaises(NotImplementedError):
            asyncio.run(run_simulation(self.config))


if __name__ == "__main__":
    unittest.main()
