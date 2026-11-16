import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.runner import _validate_frozen_inputs


class FreezeGuardTests(unittest.TestCase):
    def check_guard(self, actual_provider, actual_snapshot):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            try:
                os.chdir(temp)
                q = Path("questions.jsonl")
                q.write_text("{}\n")
                Path("results").mkdir()
                Path("results/run_manifest.json").write_text(json.dumps({"schema_version": 1, "files": {},
                    "suites": {"core": {"frozen": True, "baseline_config": "D0", "selected_config": "D0",
                        "benchmark_sha256": hashlib.sha256(q.read_bytes()).hexdigest(),
                        "snapshot_rows_sha256": "expected", "model": "test", "provider": "wafer"}}}))
                with patch("dotenv.load_dotenv"), patch.dict(os.environ, {
                        "OPENROUTER_MODEL": "test", "OPENROUTER_ALLOW_FALLBACKS": "false"}), \
                        patch("src.freeze.effective_provider", return_value=actual_provider), \
                        patch("src.freeze.live_snapshot", return_value=actual_snapshot):
                    _validate_frozen_inputs("core", "D0", q)
            finally:
                os.chdir(previous)

    def test_database_change_after_freeze_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "live database"):
            self.check_guard("wafer", "changed")

    def test_provider_change_after_freeze_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "model/provider"):
            self.check_guard("other", "expected")

    def test_matching_database_and_provider_are_accepted(self):
        self.check_guard("wafer", "expected")
