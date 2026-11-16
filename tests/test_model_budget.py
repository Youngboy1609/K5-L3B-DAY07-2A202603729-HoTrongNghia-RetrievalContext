import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from src.model import BudgetError, OpenRouterClient


class ModelBudgetTests(unittest.TestCase):
    def make_client(self, path: Path) -> OpenRouterClient:
        with patch.dict("os.environ", {
            "OPENROUTER_API_KEY": "test-key",
            "API_BUDGET_USD": "0.10",
            "API_PILOT_BUDGET_USD": "0.05",
        }):
            return OpenRouterClient(ledger_path=path, request_reserve_usd=Decimal("0.03"))

    def test_pilot_reservations_cannot_exceed_pilot_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = self.make_client(Path(tmp) / "usage.json")
            client._reserve(pilot=True, amount=client.fixed_reserve)
            client._reconcile(Decimal("0.03"), reservation=client.fixed_reserve)
            with self.assertRaises(BudgetError):
                client._reserve(pilot=True, amount=client.fixed_reserve)

    def test_unresolved_usage_blocks_next_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = self.make_client(Path(tmp) / "usage.json")
            client._reserve(pilot=True, amount=client.fixed_reserve)
            client._reconcile(None, reservation=client.fixed_reserve)
            with self.assertRaises(BudgetError):
                client._reserve(pilot=True, amount=client.fixed_reserve)

    def test_unknown_usage_can_only_be_reconciled_at_full_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key", "API_BUDGET_USD": "0.10",
                                            "API_PILOT_BUDGET_USD": "0.05"}):
                client = OpenRouterClient(ledger_path=Path(tmp) / "usage.json", request_reserve_usd=Decimal("0.02"))
            client._reserve(pilot=True, amount=Decimal("0.01"))
            client._reconcile(Decimal("0.01"), reservation=Decimal("0.01"))
            client._reserve(pilot=True, amount=client.fixed_reserve)
            client._reconcile(None, reservation=client.fixed_reserve)
            self.assertEqual(client.reconcile_unknown_as_upper_bound(), client.fixed_reserve)
            client._reserve(pilot=True, amount=client.fixed_reserve)

    def test_ledger_never_contains_auth_or_message_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "usage.json"
            client = self.make_client(path)
            client._reserve(pilot=True, amount=client.fixed_reserve)
            client._reconcile(Decimal("0.001"), reservation=client.fixed_reserve)
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("test-key", raw)
            self.assertNotIn("private prompt", raw)
            self.assertEqual(json.loads(raw)["spent_usd"], "0.001")

    def test_workload_provider_override_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {
            "OPENROUTER_API_KEY": "test-key", "OPENROUTER_PROVIDER": "wafer",
        }):
            client = OpenRouterClient(ledger_path=Path(tmp) / "usage.json", provider_override="relace")
            self.assertEqual(client.provider, "relace")

    def test_reservation_scales_for_text_and_images(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {
            "OPENROUTER_API_KEY": "test-key",
            "API_BUDGET_USD": "1.00",
            "API_PILOT_BUDGET_USD": "0.25",
        }):
            client = OpenRouterClient(ledger_path=Path(tmp) / "usage.json")
            text = client._estimate_reservation([{"role": "user", "content": "A short request"}], None, 128)
            image = client._estimate_reservation([{"role": "user", "content": [
                {"type": "text", "text": "Describe this"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}},
            ]}], None, 128)
            self.assertLess(text, Decimal("0.03"))
            self.assertGreater(image, text)


if __name__ == "__main__":
    unittest.main()
