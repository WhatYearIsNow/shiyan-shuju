import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ExampleTests(unittest.TestCase):
    def test_synthetic_direct_measurement(self):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "examples/direct_measurement.py")],
                                capture_output=True, text=True, encoding="utf-8", check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data["data_kind"], "synthetic")
        self.assertEqual(data["value"], "10.020")
        self.assertEqual(data["uncertainty"], "0.023")
        self.assertEqual(data["unit"], "mm")
