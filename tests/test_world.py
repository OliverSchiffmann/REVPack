import unittest
from reuman import world


class TestWorld(unittest.TestCase):

    def test_now_func(self):
        testWorld = world.World()
        modelTimeStep = testWorld._now
        funcTimeStep = testWorld.now()
        self.assertEqual(modelTimeStep, funcTimeStep)


if __name__ == "__main_":
    unittest.main()
