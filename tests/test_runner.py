import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.model import BudgetError
from src.runner import run_dev


class FakeAgent:
    def __init__(self, stop_after):
        self.calls = 0
        self.stop_after = stop_after

    def run(self, question, **kwargs):
        if self.calls == self.stop_after:
            raise BudgetError("blocked")
        self.calls += 1
        return {"query_id": kwargs["query_id"], "errors": [], "status": "complete",
                "split": kwargs["split"], "cost_usd": "0", "latency_ms": {"total": 1}}


class RunnerBudgetTests(unittest.TestCase):
    def test_budget_block_writes_incomplete_summary_and_preserves_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            questions = Path(temp) / "questions.jsonl"
            questions.write_text("".join(json.dumps({"id": f"q{i}", "question": f"Question {i}",
                                                       "split": "dev", "answerable": False,
                                                       "gold": [], "absence_reason": "outside corpus"}) + "\n"
                                         for i in range(3)))
            output = Path(temp) / "run.jsonl"
            agent = FakeAgent(stop_after=1)
            with patch("src.runner.create_agent", return_value=agent):
                summary = run_dev("core", "D0", questions_path=questions, output_path=output)
            self.assertEqual(summary["status"], "incomplete_budget_blocked")
            self.assertEqual(summary["pending_query_ids"], ["q1", "q2"])
            self.assertEqual(len(output.read_text().splitlines()), 1)
            self.assertTrue(output.with_suffix(".summary.json").exists())

    def test_test_split_runs_only_test_rows_and_records_run_id(self):
        with tempfile.TemporaryDirectory() as temp:
            questions = Path(temp) / "questions.jsonl"
            rows = [{"id": "dev", "question": "Dev", "split": "dev", "answerable": False,
                     "gold": [], "absence_reason": "outside corpus"},
                    {"id": "test", "question": "Test", "split": "test", "answerable": False,
                     "gold": [], "absence_reason": "outside corpus"}]
            questions.write_text("".join(json.dumps(row) + "\n" for row in rows))
            output = Path(temp) / "run.jsonl"
            with patch("src.runner._validate_frozen_inputs"), \
                    patch("src.runner.create_agent", return_value=FakeAgent(stop_after=10)):
                summary = run_dev("core", "D0", split="test", questions_path=questions, output_path=output)
            trace = json.loads(output.read_text().splitlines()[0])
            self.assertEqual(summary["split"], "test")
            self.assertEqual(summary["n"], 1)
            self.assertEqual(trace["query_id"], "test")
            self.assertEqual(trace["split"], "test")
            self.assertEqual(trace["run_id"], summary["run_id"])


if __name__ == "__main__":
    unittest.main()
