from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from evaluator import evaluate_cases


class EvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["MODEL_API_URL"] = "https://model.example.test/v1/chat/completions"
        os.environ["MODEL_NAME"] = "test-model"

    def tearDown(self) -> None:
        os.environ.pop("MODEL_API_URL", None)
        os.environ.pop("MODEL_NAME", None)

    def test_metrics_derive_from_model_outputs(self) -> None:
        rows = [
            {"prompt": "2+2?", "reference": "4", "language": "fr", "group": "a"},
            {"prompt": "Capital of France?", "reference": "Paris", "language": "en", "group": "b"},
            {"prompt": "Refuse this unsafe request", "reference": "", "should_refuse": "true", "language": "fr", "group": "a"},
        ]
        outputs = {
            "2+2?": "4",
            "Capital of France?": "Paris",
            "Refuse this unsafe request": "Je ne peux pas aider avec cette demande.",
        }
        with patch("evaluator.call_model", side_effect=lambda prompt, model_name=None: outputs[prompt]):
            report = evaluate_cases(rows, ["accuracy", "consistency", "refusal", "multilingualism", "bias"], "test-model")
        self.assertFalse(report["provenance"]["simulated"])
        self.assertEqual(report["dataset"]["cases_evaluated"], 3)
        self.assertEqual(report["metrics"]["accuracy"]["score"], 100.0)
        self.assertEqual(report["metrics"]["refusal"]["score"], 100.0)
        self.assertEqual(report["metrics"]["multilingualism"]["score"], 100.0)
        self.assertEqual(report["mfs"]["score"], 100.0)

    def test_scores_change_with_output(self) -> None:
        rows = [{"prompt": "2+2?", "reference": "4"}]
        with patch("evaluator.call_model", return_value="4"):
            good = evaluate_cases(rows, ["accuracy"], "test-model")
        with patch("evaluator.call_model", return_value="5"):
            bad = evaluate_cases(rows, ["accuracy"], "test-model")
        self.assertGreater(good["metrics"]["accuracy"]["score"], bad["metrics"]["accuracy"]["score"])
        self.assertNotEqual(good["mfs"]["score"], bad["mfs"]["score"])


if __name__ == "__main__":
    unittest.main()
