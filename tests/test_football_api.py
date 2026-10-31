"""Tests de l'API et du cache, sans appel réel à Internet (réponses simulées)."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from database import db
from services import cache
from services.data_manager import DataManager
from services.football_api import ApiError, FootballApiClient, normalize_fixture

RAW_FIXTURE = {
    "fixture": {"id": 1001, "date": "2026-11-01T16:00:00+01:00", "status": {"short": "FT"}},
    "league": {"id": 39, "name": "Premier League", "country": "England", "season": 2026, "round": "Regular Season - 9"},
    "teams": {"home": {"id": 33, "name": "Manchester United"}, "away": {"id": 40, "name": "Liverpool"}},
    "goals": {"home": 1, "away": 2},
}


class FakeResponse:
    def __init__(self, status=200, data=None, headers=None):
        self.status_code = status
        self._data = data if data is not None else {"errors": [], "response": []}
        self.headers = headers or {}

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, response=None, exc=None):
        self.response, self.exc, self.calls = response, exc, []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        if self.exc:
            raise self.exc
        return self.response


class NormalizeTests(unittest.TestCase):
    def test_fixture_is_normalized_to_utc(self):
        fx = normalize_fixture(RAW_FIXTURE)
        self.assertEqual(fx["kickoff_utc"], "2026-11-01T15:00:00+00:00")
        self.assertEqual(fx["status"], "finished")
        self.assertEqual((fx["home_goals"], fx["away_goals"]), (1, 2))

    def test_unknown_status_becomes_other(self):
        raw = {**RAW_FIXTURE, "fixture": {**RAW_FIXTURE["fixture"], "status": {"short": "XYZ"}}}
        self.assertEqual(normalize_fixture(raw)["status"], "other")

    def test_missing_field_raises_value_error(self):
        with self.assertRaises(ValueError):
            normalize_fixture({"fixture": {"id": 1}})


class ClientTests(unittest.TestCase):
    def test_sends_api_key_header_and_parses_fixtures(self):
        session = FakeSession(FakeResponse(data={"errors": [], "response": [RAW_FIXTURE]},
                                           headers={"x-ratelimit-requests-remaining": "87"}))
        client = FootballApiClient(api_key="SECRET", base_url="https://example.test/v3/", session=session)
        fixtures = client.fixtures_by_date(date(2026, 11, 1))
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(session.calls[0][2]["x-apisports-key"], "SECRET")
        self.assertEqual(client.requests_remaining, "87")

    def test_missing_key_never_calls_network(self):
        session = FakeSession()
        client = FootballApiClient(api_key="", session=session)
        with self.assertRaises(ApiError):
            client.fixtures_by_date(date(2026, 11, 1))
        self.assertEqual(session.calls, [])

    def test_http_errors_are_translated(self):
        for status in (401, 429, 500):
            client = FootballApiClient(api_key="K", session=FakeSession(FakeResponse(status=status)))
            with self.assertRaises(ApiError):
                client.fixtures_by_date(date(2026, 11, 1))

    def test_api_error_payload_is_raised(self):
        resp = FakeResponse(data={"errors": {"requests": "Quota exceeded"}, "response": []})
        client = FootballApiClient(api_key="K", session=FakeSession(resp))
        with self.assertRaises(ApiError):
            client.fixtures_by_date(date(2026, 11, 1))

    def test_connection_failure_is_translated(self):
        import requests
        client = FootballApiClient(api_key="K", session=FakeSession(exc=requests.ConnectionError()))
        with self.assertRaises(ApiError):
            client.fixtures_by_date(date(2026, 11, 1))


class CacheAndSyncTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self._tmp.name) / "t.db")

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_cache_expiry(self):
        cache.set(self.conn, "k", {"a": 1}, "test", ttl_seconds=3600)
        self.assertEqual(cache.get(self.conn, "k"), {"a": 1})
        cache.set(self.conn, "old", [1], "test", ttl_seconds=-10)
        self.assertIsNone(cache.get(self.conn, "old"))
        self.assertEqual(cache.get(self.conn, "old", allow_expired=True), [1])

    def test_sync_stores_matches_without_duplicates(self):
        session = FakeSession(FakeResponse(data={"errors": [], "response": [RAW_FIXTURE]}))
        manager = DataManager(self.conn, FootballApiClient(api_key="K", session=session))
        first = manager.sync_fixtures_for_date(date(2026, 11, 1))
        second = manager.sync_fixtures_for_date(date(2026, 11, 1))
        self.assertEqual(first.count, 1)
        self.assertTrue(second.from_cache)              # 2e appel servi par le cache
        self.assertEqual(len(session.calls), 1)         # un seul appel réseau
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0], 2)

    def test_offline_falls_back_to_old_cache(self):
        cache.set(self.conn, "fixtures:2026-11-01", [], "test", ttl_seconds=-10)
        import requests
        session = FakeSession(exc=requests.ConnectionError())
        manager = DataManager(self.conn, FootballApiClient(api_key="K", session=session))
        result = manager.sync_fixtures_for_date(date(2026, 11, 1))
        self.assertTrue(result.offline)
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
