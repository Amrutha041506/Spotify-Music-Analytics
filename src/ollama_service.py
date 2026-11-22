"""Optional Ollama integration (local LLM). The core project never needs this module.

The model is only given pre-computed facts and told not to invent numbers.
Replies are post-checked: numbers that do not appear in the facts are reported
as warnings so the user can see when the model went beyond the data.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

import requests

from src.insights import answer_question_rule_based

SYSTEM_PROMPT = """You are a careful music-analytics assistant.
Rules you must follow:
1. Use ONLY the numbers and names found in the FACTS JSON provided by the user message.
2. If the facts do not contain the answer, reply exactly: "That is not available in the computed results."
3. Never invent, estimate or round numbers differently from the facts.
4. Correlation is not causation. Describe relationships as 'associated with', never 'causes'.
5. Mention when a figure comes from a minimum-track-count filter if it matters.
6. Keep answers short, factual and in plain language."""


class OllamaError(Exception):
    """Base class for Ollama problems."""


class OllamaUnavailableError(OllamaError):
    """Ollama is not running / not reachable."""


class OllamaModelNotFoundError(OllamaError):
    """The configured model has not been pulled."""


@dataclass
class OllamaSettings:
    host: str = "http://localhost:11434"
    model: str = "llama3.1"
    timeout_seconds: float = 120
    temperature: float = 0.1

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "OllamaSettings":
        section = cfg.get("ollama", {})
        return cls(
            host=str(section.get("host", cls.host)).rstrip("/"),
            model=section.get("model", cls.model),
            timeout_seconds=float(section.get("timeout_seconds", cls.timeout_seconds)),
            temperature=float(section.get("temperature", cls.temperature)),
        )


@dataclass
class OllamaAnswer:
    text: str
    source: str                      # "ollama" or "rule_based"
    model: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None


# --------------------------------------------------------------------------- #
# Number checking
# --------------------------------------------------------------------------- #
_NUMBER_RE = re.compile(r"(?<![\w.])-?\d[\d,]*\.?\d*")


def _collect_numbers(obj: Any, bag: Set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        bag.add(float(obj))
    elif isinstance(obj, dict):
        for value in obj.values():
            _collect_numbers(value, bag)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _collect_numbers(value, bag)
    elif isinstance(obj, str):
        for match in _NUMBER_RE.findall(obj):
            try:
                bag.add(float(match.replace(",", "")))
            except ValueError:
                pass


def find_unsupported_numbers(answer: str, facts: Dict[str, Any]) -> List[str]:
    """Numbers in `answer` that cannot be matched to any number in `facts`.

    Small integers (1-10) are ignored because they are usually list numbering.
    A number matches if it equals a fact value after rounding to the answer's precision.
    """
    known: Set[float] = set()
    _collect_numbers(facts, known)
    unsupported = []
    for raw in _NUMBER_RE.findall(answer):
        text = raw.replace(",", "").rstrip(".")
        try:
            value = float(text)
        except ValueError:
            continue
        if value.is_integer() and 1 <= abs(value) <= 10 and "." not in text:
            continue
        decimals = len(text.split(".")[1]) if "." in text else 0
        tolerance = 0.5 * 10 ** (-decimals) + 1e-9
        if not any(abs(value - k) <= tolerance for k in known):
            unsupported.append(raw)
    return unsupported


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class OllamaClient:
    def __init__(self, settings: Optional[OllamaSettings] = None, session: Optional[requests.Session] = None):
        self.settings = settings or OllamaSettings()
        self._http = session or requests.Session()

    def _url(self, path: str) -> str:
        return f"{self.settings.host}{path}"

    def _unavailable(self, exc: Exception) -> OllamaUnavailableError:
        return OllamaUnavailableError(
            f"Ollama is not reachable at {self.settings.host}. Install it from https://ollama.com, start it "
            f"(`ollama serve`) and pull a model (`ollama pull {self.settings.model}`). Details: {exc}"
        )

    def list_models(self) -> List[str]:
        try:
            response = self._http.get(self._url("/api/tags"), timeout=5)
            response.raise_for_status()
            return [m["name"] for m in response.json().get("models", [])]
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise self._unavailable(exc) from exc
        except (requests.RequestException, ValueError, KeyError) as exc:
            raise OllamaError(f"Unexpected response from Ollama: {exc}") from exc

    def is_available(self) -> bool:
        try:
            self.list_models()
            return True
        except OllamaError:
            return False

    def has_model(self) -> bool:
        wanted = self.settings.model
        return any(name == wanted or name.split(":")[0] == wanted for name in self.list_models())

    def chat(self, messages: List[Dict[str, str]]) -> str:
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.settings.temperature},
        }
        try:
            response = self._http.post(self._url("/api/chat"), json=payload, timeout=self.settings.timeout_seconds)
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise self._unavailable(exc) from exc
        except requests.RequestException as exc:
            raise OllamaError(f"Request to Ollama failed: {exc}") from exc

        if response.status_code == 404:
            raise OllamaModelNotFoundError(
                f"Model '{self.settings.model}' is not installed. Run: ollama pull {self.settings.model}"
            )
        if not response.ok:
            raise OllamaError(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")
        try:
            return response.json()["message"]["content"].strip()
        except (ValueError, KeyError, TypeError) as exc:
            raise OllamaError("Ollama returned an unreadable response.") from exc

    def ask(self, question: str, facts: Dict[str, Any]) -> OllamaAnswer:
        user_message = (
            f"FACTS (JSON, computed with pandas from the cleaned dataset):\n{json.dumps(facts, default=str)}\n\n"
            f"QUESTION: {question}"
        )
        text = self.chat([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ])
        warnings = []
        unsupported = find_unsupported_numbers(text, facts)
        if unsupported:
            warnings.append(
                "These numbers could not be matched to the computed results - verify before use: "
                + ", ".join(unsupported)
            )
        return OllamaAnswer(text=text, source="ollama", model=self.settings.model, warnings=warnings)


def answer_with_fallback(question: str, facts: Dict[str, Any], client: Optional[OllamaClient]) -> OllamaAnswer:
    """Try Ollama; on any Ollama problem return the rule-based answer plus the reason."""
    if client is not None:
        try:
            return client.ask(question, facts)
        except OllamaError as exc:
            return OllamaAnswer(text=answer_question_rule_based(question, facts), source="rule_based", error=str(exc))
    return OllamaAnswer(text=answer_question_rule_based(question, facts), source="rule_based",
                        error="Ollama integration is disabled.")
