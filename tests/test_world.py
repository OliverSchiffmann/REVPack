import unittest
from reuman import world,customer


class TestWorld(unittest.TestCase):

    def test_now_func(self):
        testWorld = world.World()
        modelTimeStep = testWorld._now
        funcTimeStep = testWorld.now()
        self.assertEqual(modelTimeStep, funcTimeStep)

    def test_add_agent(self):
        # Test to see whether adding an agent actually adds the right agent with the right params
        testWorld = world.World()
        # testAgent = 

    
if __name__ == "__main_":
    unittest.main()
