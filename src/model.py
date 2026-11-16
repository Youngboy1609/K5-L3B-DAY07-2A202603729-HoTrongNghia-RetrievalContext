"""Small OpenRouter chat client with a fail-closed local spending guard."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


class BudgetError(RuntimeError):
    """Raised before a request when its worst-case reservation exceeds budget."""


class UsageError(RuntimeError):
    """Raised when provider usage/cost cannot be established safely."""


@dataclass(frozen=True)
class ModelResponse:
    data: dict[str, Any]
    cost_usd: Decimal
    elapsed_ms: float


class OpenRouterClient:
    """OpenAI-compatible client pinned to the selected model/provider.

    Each request reserves ``request_reserve_usd`` before sending and reconciles
    against the provider-reported cost before releasing the reservation. The
    ledger is local-only; it never contains the API key or message contents.
    """

    endpoint = "https://openrouter.ai/api/v1/chat/completions"
    # Wafer / GLM 5.3 Flash prices checked against OpenRouter's endpoint catalog on 2026-11-16.
    input_price_per_million = Decimal("0.042")
    output_price_per_million = Decimal("0.184")
    image_token_reserve = 20_000

    def __init__(self, *, ledger_path: str | Path = ".lab-local/usage-ledger.json",
                 request_reserve_usd: Decimal | None = None,
                 provider_override: str | None = None) -> None:
        load_dotenv(override=False)
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is missing")
        self.model = os.environ.get("OPENROUTER_MODEL", "z-ai/glm-5.3-flash")
        self.provider = (provider_override or os.environ.get("OPENROUTER_PROVIDER", "wafer")).strip().lower()
        self.allow_fallbacks = os.environ.get("OPENROUTER_ALLOW_FALLBACKS", "false").lower() == "true"
        self.total_budget = Decimal(os.environ.get("API_BUDGET_USD", "1.00"))
        self.pilot_budget = Decimal(os.environ.get("API_PILOT_BUDGET_USD", "0.25"))
        self.ledger_path = Path(ledger_path)
        self.fixed_reserve = request_reserve_usd
        if (self.fixed_reserve is not None and self.fixed_reserve <= 0) or self.total_budget <= 0 or self.pilot_budget <= 0:
            raise ValueError("Budgets/reservation must be positive")
        self._lock = threading.Lock()

    def _estimate_reservation(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None,
                              max_tokens: int) -> Decimal:
        if self.fixed_reserve is not None:
            return self.fixed_reserve
        text_bytes = len(json.dumps(tools or [], ensure_ascii=False).encode("utf-8"))
        image_count = 0
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, str):
                text_bytes += len(content.encode("utf-8"))
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "image_url":
                        image_count += 1
                        url = part.get("image_url", {}).get("url", "")
                        if url.startswith("data:") and len(url) > 5_000_000:
                            raise ValueError("inline image exceeds the 5 MB request limit")
                    else:
                        text_bytes += len(str(part.get("text", "")).encode("utf-8"))
        input_tokens = text_bytes + image_count * self.image_token_reserve
        estimated = (Decimal(input_tokens) * self.input_price_per_million
                     + Decimal(max_tokens) * self.output_price_per_million) / Decimal(1_000_000)
        return max(Decimal("0.00002"), estimated * Decimal("2"))

    def _read_ledger(self) -> dict[str, Any]:
        if not self.ledger_path.exists():
            return {"schema_version": 1, "spent_usd": "0", "reserved_usd": "0", "calls": []}
        data = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1 or not isinstance(data.get("calls"), list):
            raise UsageError("Usage ledger is invalid; refusing API call")
        return data

    def _write_ledger(self, data: dict[str, Any]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.ledger_path.with_suffix(self.ledger_path.suffix + ".tmp")
        temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        temp.replace(self.ledger_path)

    def _reserve(self, pilot: bool, amount: Decimal) -> None:
        with self._lock:
            ledger = self._read_ledger()
            if ledger.get("budget_blocked"):
                raise BudgetError("Usage is unresolved or the spending cap was reached; refusing request")
            spent = Decimal(ledger["spent_usd"])
            reserved = Decimal(ledger["reserved_usd"])
            cap = min(self.total_budget, self.pilot_budget) if pilot else self.total_budget
            if spent + reserved + amount > cap:
                raise BudgetError(f"Request reservation would exceed {'pilot' if pilot else 'total'} cap")
            ledger["reserved_usd"] = str(reserved + amount)
            ledger["calls"].append({"status": "reserved", "reservation_usd": str(amount),
                                    "pilot": pilot, "at": time.time()})
            self._write_ledger(ledger)

    def _reconcile(self, cost: Decimal | None, *, failure: str | None = None,
                   reservation: Decimal | None = None) -> None:
        with self._lock:
            ledger = self._read_ledger()
            pending = next((c for c in reversed(ledger["calls"]) if c.get("status") == "reserved"), None)
            amount = reservation if reservation is not None else Decimal(pending["reservation_usd"]) if pending else Decimal("0")
            ledger["reserved_usd"] = str(max(Decimal("0"), Decimal(ledger["reserved_usd"]) - amount))
            call = pending or ledger["calls"][-1]
            if cost is None:
                call.update({"status": "unknown_cost", "error_type": failure or "missing_usage_cost"})
                ledger["budget_blocked"] = True
            else:
                spent = Decimal(ledger["spent_usd"]) + cost
                ledger["spent_usd"] = str(spent)
                call.update({"status": "complete", "cost_usd": str(cost)})
                if spent >= self.total_budget:
                    ledger["budget_blocked"] = True
            self._write_ledger(ledger)

    def reconcile_unknown_as_upper_bound(self) -> Decimal:
        """Resolve the latest unknown call by counting its full reservation as spent.

        This is deliberately conservative: it permits no retry until the caller
        explicitly chooses the safe upper bound rather than guessing the charge.
        """
        with self._lock:
            ledger = self._read_ledger()
            pending = next((c for c in reversed(ledger["calls"]) if c.get("status") == "unknown_cost"), None)
            if pending is None:
                raise UsageError("there is no unknown-cost request to reconcile")
            bound = Decimal(pending["reservation_usd"])
            spent = Decimal(ledger["spent_usd"]) + bound
            ledger["spent_usd"] = str(spent)
            ledger["reserved_usd"] = str(max(Decimal("0"), Decimal(ledger["reserved_usd"]) - bound))
            pending.update({"status": "reconciled_upper_bound", "cost_usd": str(bound),
                            "reconciliation": "full request reservation counted as spent"})
            ledger["budget_blocked"] = spent >= self.total_budget
            self._write_ledger(ledger)
            return bound

    def chat(self, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None,
             tool_choice: str | dict[str, Any] | None = None, max_tokens: int = 256,
             pilot: bool = False, timeout: float = 60) -> ModelResponse:
        if not 1 <= max_tokens <= 2048:
            raise ValueError("max_tokens must be between 1 and 2048")
        if not messages or not all(isinstance(m, dict) for m in messages):
            raise ValueError("messages must be non-empty chat objects")
        reservation = self._estimate_reservation(messages, tools, max_tokens)
        self._reserve(pilot, reservation)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "provider": {"only": [self.provider], "sort": "price", "require_parameters": True,
                         "allow_fallbacks": self.allow_fallbacks},
            "usage": {"include": True},
        }
        if tools:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read())
            usage = data.get("usage") or {}
            raw_cost = usage.get("cost")
            if raw_cost is None:
                self._reconcile(None, reservation=reservation)
                raise UsageError("Provider response omitted usage.cost; API usage is now blocked")
            cost = Decimal(str(raw_cost))
            if cost < 0 or cost > reservation:
                self._reconcile(cost, reservation=reservation)
                with self._lock:
                    ledger = self._read_ledger()
                    ledger["budget_blocked"] = True
                    self._write_ledger(ledger)
                raise BudgetError("Reported request cost exceeded its reservation; future calls blocked")
            self._reconcile(cost, reservation=reservation)
            return ModelResponse(data, cost, (time.perf_counter() - started) * 1000)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(raw)
                detail = parsed.get("error", {}).get("message", "")
            except (json.JSONDecodeError, AttributeError):
                detail = ""
            if self.api_key:
                detail = detail.replace(self.api_key, "[REDACTED]")
            self._reconcile(None, failure=f"http_{exc.code}", reservation=reservation)
            suffix = f": {detail[:300]}" if detail else ""
            raise RuntimeError(f"OpenRouter returned HTTP {exc.code}{suffix}; usage must be reconciled before retry") from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.gaierror, ConnectionRefusedError)):
                self._reconcile(Decimal("0"), reservation=reservation)
                raise RuntimeError(f"OpenRouter connection was not established; request was not sent: {exc.reason}") from None
            self._reconcile(None, failure="network_error", reservation=reservation)
            raise RuntimeError("OpenRouter network error after connection attempt; cost unknown, calls blocked") from None
        except (TimeoutError, json.JSONDecodeError) as exc:
            self._reconcile(None, failure=type(exc).__name__, reservation=reservation)
            raise RuntimeError("OpenRouter response failed; cost status unknown, calls blocked") from None

