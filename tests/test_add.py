import unittest
from reuman import add


class TestAddFunc(unittest.TestCase):

    def test_add(self):
        ans = add(1, 2)
        self.assertEqual(ans, 3)


if __name__ == "__main_":
    unittest.main()
