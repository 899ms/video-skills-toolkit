import importlib.util
import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SKILL_DIR / "scripts" / "calculate_virality.py"
EVAL_PATH = SKILL_DIR / "evals" / "cases.json"


def load_module():
    spec = importlib.util.spec_from_file_location("calculate_virality", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EvalCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()
        cls.cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))

    def test_all_cases_match_expected_classification(self):
        for case in self.cases:
            with self.subTest(case=case["name"]):
                result = self.module.calculate(case["input"])
                for key, expected in case["expected"].items():
                    self.assertEqual(result[key], expected)


if __name__ == "__main__":
    unittest.main()
