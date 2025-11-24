import unittest
import os
import sys
# Add src to path so we can import robocrew
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from robocrew.core.memory import Memory

class TestMemory(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_memory.db"
        self.memory = Memory(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_add_and_search_memory(self):
        self.memory.add_memory("The kitchen is on the first floor.")
        self.memory.add_memory("The bedroom is on the second floor.")
        
        results = self.memory.search_memory("kitchen")
        self.assertIn("kitchen", results)
        self.assertNotIn("bedroom", results)

    def test_search_no_results(self):
        results = self.memory.search_memory("garage")
        self.assertIn("No matching memories found", results)

if __name__ == '__main__':
    unittest.main()
