import tempfile
import unittest
from pathlib import Path
from train import cosine_factor, create_run_dir


class TrainingReportTests(unittest.TestCase):
    def test_cosine_endpoints(self):
        values = [cosine_factor(i, 10, .01) for i in range(10)]
        self.assertAlmostEqual(values[0],1)
        self.assertAlmostEqual(values[-1],.01)
        self.assertTrue(all(a>=b for a,b in zip(values,values[1:])))
        self.assertEqual(cosine_factor(0,1,.01),1)

    def test_output_preserves_existing(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'custom'
            self.assertEqual(create_run_dir(str(path),'dataset'),path)
            with self.assertRaises(ValueError):
                create_run_dir(str(path),'dataset')
