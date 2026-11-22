"""Tests for the optional Ollama integration (no real Ollama server needed)."""
import unittest
from unittest import mock

import requests

from src.ollama_service import (OllamaClient, OllamaError, OllamaModelNotFoundError, OllamaSettings,
                                OllamaUnavailableError, answer_with_fallback, find_unsupported_numbers)

FACTS = {"dataset": {"avg_popularity": 33.45, "unique_tracks": 114000},
         "top_genres_by_popularity": [{"track_genre": "pop-film", "avg_popularity": 59.28}], "settings": {"min_tracks_genre": 20},
         "top_artists_by_avg_popularity": [], "popularity_correlations": [], "notes": []}


def fake_response(status=200, payload=None, text=""):
    response = mock.Mock(status_code=status, ok=status < 400, text=text)
    response.json.return_value = payload or {}
    response.raise_for_status.side_effect = None if status < 400 else requests.HTTPError()
    return response


class TestOllamaClient(unittest.TestCase):
    def test_real_connection_refused_gives_clear_message(self):
        client = OllamaClient(OllamaSettings(host="http://127.0.0.1:9"))  # nothing listens on port 9
        self.assertFalse(client.is_available())
        with self.assertRaises(OllamaUnavailableError) as ctx:
            client.chat([{"role": "user", "content": "hi"}])
        self.assertIn("ollama serve", str(ctx.exception))

    def test_list_models_and_has_model(self):
        session = mock.Mock()
        session.get.return_value = fake_response(payload={"models": [{"name": "llama3.1:latest"}]})
        client = OllamaClient(OllamaSettings(model="llama3.1"), session=session)
        self.assertEqual(client.list_models(), ["llama3.1:latest"])
        self.assertTrue(client.has_model())
        client.settings.model = "mistral"
        self.assertFalse(client.has_model())

    def test_model_not_found(self):
        session = mock.Mock()
        session.post.return_value = fake_response(status=404)
        with self.assertRaises(OllamaModelNotFoundError) as ctx:
            OllamaClient(OllamaSettings(model="nope"), session=session).chat([])
        self.assertIn("ollama pull nope", str(ctx.exception))

    def test_timeout_is_reported_as_unavailable(self):
        session = mock.Mock()
        session.post.side_effect = requests.Timeout("slow")
        with self.assertRaises(OllamaUnavailableError):
            OllamaClient(session=session).chat([])

    def test_malformed_response_raises_ollama_error(self):
        session = mock.Mock()
        session.post.return_value = fake_response(payload={"unexpected": True})
        with self.assertRaises(OllamaError):
            OllamaClient(session=session).chat([])

    def test_ask_sends_facts_and_flags_invented_numbers(self):
        session = mock.Mock()
        session.post.return_value = fake_response(
            payload={"message": {"content": "Average popularity is 33.45 but pop has 99.9 listeners."}})
        client = OllamaClient(OllamaSettings(model="llama3.1", temperature=0.0), session=session)
        answer = client.ask("What is average popularity?", FACTS)
        sent = session.post.call_args.kwargs["json"]
        self.assertFalse(sent["stream"])
        self.assertIn("FACTS", sent["messages"][1]["content"])
        self.assertIn("33.45", sent["messages"][1]["content"])
        self.assertEqual(answer.source, "ollama")
        self.assertEqual(len(answer.warnings), 1)
        self.assertIn("99.9", answer.warnings[0])

    def test_fallback_used_when_ollama_down(self):
        client = OllamaClient(OllamaSettings(host="http://127.0.0.1:9"))
        answer = answer_with_fallback("Which genre has the highest popularity?", FACTS, client)
        self.assertEqual(answer.source, "rule_based")
        self.assertIn("pop-film", answer.text)
        self.assertIn("not reachable", answer.error)

    def test_fallback_when_integration_disabled(self):
        answer = answer_with_fallback("Which genre is most popular?", FACTS, None)
        self.assertEqual(answer.source, "rule_based")


class TestNumberChecking(unittest.TestCase):
    def test_supported_numbers_pass(self):
        self.assertEqual(find_unsupported_numbers("Average is 33.45 over 114,000 tracks; about 33 overall.", FACTS), [])

    def test_unsupported_numbers_flagged_and_list_numbers_ignored(self):
        self.assertEqual(find_unsupported_numbers("1. pop 2. rock: 88.8", FACTS), ["88.8"])


class TestSettings(unittest.TestCase):
    def test_settings_from_config_strip_trailing_slash(self):
        s = OllamaSettings.from_config({"ollama": {"host": "http://h:1/", "model": "m", "timeout_seconds": 5, "temperature": 0.3}})
        self.assertEqual((s.host, s.model, s.timeout_seconds, s.temperature), ("http://h:1", "m", 5.0, 0.3))


if __name__ == "__main__":
    unittest.main()
