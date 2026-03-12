import unittest
from reuman import divide


class TestAddFunc(unittest.TestCase):

    def test_divide(self):
        ans = divide(2, 1)
        self.assertEqual(ans, 2)


if __name__ == "__main_":
    unittest.main()
