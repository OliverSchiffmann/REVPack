import unittest
import os
import re
import warnings

class TestWebappSync(unittest.TestCase):
    """
    Tests to ensure that parameters defined in the Python backend (scenarios.py)
    are correctly exposed in the frontend web application (index.html).
    """

    def setUp(self):
        # Attempt to import SCENARIOS from examples.scenarios
        try:
            from examples.scenarios import SCENARIOS
            self.default_scenario = SCENARIOS.get("Default", {})
        except ImportError:
            self.skipTest("Could not import SCENARIOS from examples.scenarios. Make sure you run tests from the root directory.")
        
        if not self.default_scenario:
            self.skipTest("No 'Default' scenario found in SCENARIOS.")

        # Find index.html relative to this test file
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.index_path = os.path.join(base_dir, "index.html")
        
        self.assertTrue(os.path.exists(self.index_path), f"Could not find index.html at {self.index_path}")

        with open(self.index_path, "r", encoding="utf-8") as f:
            self.index_content = f.read()

    def test_parameters_in_paramSchema(self):
        """Check if all parameters in the default scenario exist in index.html's paramSchema."""
        # Extract the paramSchema block from index.html
        schema_match = re.search(r'const paramSchema = \{(.*?)\};\s*(?:const|let) defaultConfig', self.index_content, re.DOTALL)
        if schema_match is None:
            self.fail("Could not find 'paramSchema' block in index.html")
        schema_block = schema_match.group(1)

        missing_params = []
        categories = ["main", "oem", "b2b_customer", "b2c_customer"]

        for category in categories:
            if category in self.default_scenario:
                for param in self.default_scenario[category]:
                    # Regex to look for the parameter key in the JS object (e.g., "simulation_length:")
                    pattern = rf'\b{param}\s*:'
                    if not re.search(pattern, schema_block):
                        missing_params.append(f"{category} -> {param}")

        if missing_params:
            warnings.warn(
                f"The following parameters from the 'Default' scenario are missing in index.html's paramSchema:\n{chr(10).join(missing_params)}"
            )

if __name__ == "__main__":
    unittest.main()