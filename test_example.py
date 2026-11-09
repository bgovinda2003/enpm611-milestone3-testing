import unittest

class TestExample(unittest.TestCase):    
    def test_normal_calculation(self):        
        actual = sum([2, 3, 5])        
        self.assertEqual(actual, 10)    
    def test_empty_collection(self):        
        actual = sum([])        
        self.assertEqual(actual, 0)    
    def test_invalid_input(self):        
        with self.assertRaises(TypeError):            
            sum([1, None])
if __name__ == "__main__":    
    unittest.main()