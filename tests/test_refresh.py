"""Tests de l'actualisation : budget de requêtes, mode hors ligne, verrouillage et évaluation."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from database import db, queries
from engine import evaluation, prediction
from services.data_manager import MAX_REQUESTS_PER_REFRESH, refresh_all
from services.football_api import FootballApiClient
from tests.test_football_api import FakeResponse, FakeSession

import requests

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def raw(fid, home, away, date, short="FT", hg=2, ag=1):
    return {"fixture": {"id": fid, "date": date, "status": {"short": short}},
            "league": {"id": 39, "name": "PL", "country": "England", "season": 2026, "round": "R1"},
            "teams": {"home": {"id": home, "name": f"T{home}"}, "away": {"id": away, "name": f"T{away}"}},
            "goals": {"home": hg, "away": ag}}


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self._tmp.name) / "r.db")

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_offline_refresh_uses_local_data_and_reports_it(self):
        session = FakeSession(exc=requests.ConnectionError())
        client = FootballApiClient(api_key="K", session=session)
        report = refresh_all(self.conn, client, now=NOW)
        self.assertTrue(report.offline)
        self.assertTrue(report.errors)
        self.assertIn("Connexion impossible", report.messages[0])

    def test_refresh_never_exceeds_request_budget(self):
        session = FakeSession(FakeResponse(data={"errors": [], "response": []}))
        client = FootballApiClient(api_key="K", session=session)
        report = refresh_all(self.conn, client, now=NOW)
        self.assertLessEqual(report.requests_used, MAX_REQUESTS_PER_REFRESH)

    def test_without_key_nothing_is_sent(self):
        session = FakeSession()
        client = FootballApiClient(api_key="", session=session)
        report = refresh_all(self.conn, client, now=NOW)
        self.assertEqual(session.calls, [])
        self.assertTrue(report.errors)

    def test_refresh_stores_results_and_evaluates_predictions(self):
        # Un match passé, terminé, puis une analyse enregistrée avant son coup d'envoi
        comp = db.upsert_competition(self.conn, 39, "PL", "England", 2026, "league", "t")
        h = db.upsert_team(self.conn, 1, "A", None, "t")
        a = db.upsert_team(self.conn, 2, "B", None, "t")
        mid = db.upsert_match(self.conn, 77, comp, 2026, "R1", "2026-10-31T15:00:00+00:00",
                              "scheduled", h, a, None, None, "t")
        analysis_id, _ = prediction.predict_for_match(self.conn, mid, save=True)
        self.assertIsNotNone(analysis_id)
        # Le match se termine : le fournisseur renvoie le score final
        session = FakeSession(FakeResponse(data={"errors": [], "response": [
            raw(77, 1, 2, "2026-10-31T15:00:00+00:00", "FT", 2, 1)]}))
        client = FootballApiClient(api_key="K", session=session)
        report = refresh_all(self.conn, client, now=datetime(2026, 10, 31, 18, 0, tzinfo=timezone.utc))
        self.assertGreaterEqual(report.analyses_locked, 1)
        self.assertEqual(report.analyses_evaluated, 1)
        summary = evaluation.performance_summary(self.conn)
        self.assertEqual(summary["evaluated"], 1)
        self.assertIn("Plus de 2,5 buts", summary["by_market"])

    def test_locked_prediction_is_not_changed_by_refresh(self):
        comp = db.upsert_competition(self.conn, 39, "PL", "England", 2026, "league", "t")
        h = db.upsert_team(self.conn, 1, "A", None, "t")
        a = db.upsert_team(self.conn, 2, "B", None, "t")
        db.upsert_match(self.conn, 78, comp, 2026, "R1", "2026-10-31T10:00:00+00:00",
                        "live", h, a, None, None, "t")
        mid = self.conn.execute("SELECT id FROM matches WHERE api_id = 78").fetchone()[0]
        prediction.predict_for_match(self.conn, mid, save=True)
        locked = evaluation.lock_started_matches(self.conn, NOW.isoformat())
        self.assertEqual(locked, 1)
        self.assertEqual(evaluation.lock_started_matches(self.conn, NOW.isoformat()), 0)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self._tmp.name) / "e.db")

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_brier_and_log_loss_on_known_case(self):
        comp = db.upsert_competition(self.conn, 39, "PL", "England", 2026, "league", "t")
        h = db.upsert_team(self.conn, 1, "A", None, "t")
        a = db.upsert_team(self.conn, 2, "B", None, "t")
        mid = db.upsert_match(self.conn, 1, comp, 2026, "R", "2026-10-01T15:00:00+00:00",
                              "finished", h, a, 1, 0, "t")
        values = {"lambda_home": 1.5, "lambda_away": 1.0, "p_home": 0.5, "p_draw": 0.3,
                  "p_away": 0.2, "data_quality": "moyen"}
        from database.db import save_analysis
        analysis_id = save_analysis(self.conn, mid, "test", values)
        self.assertEqual(evaluation.evaluate_finished(self.conn), 1)
        row = self.conn.execute("SELECT * FROM evaluations WHERE analysis_id = ?", (analysis_id,)).fetchone()
        # Issue réelle : domicile. Brier = (0.5-1)^2 + (0.3-0)^2 + (0.2-0)^2 = 0.38
        self.assertAlmostEqual(row["brier_1x2"], 0.38, places=5)
        self.assertAlmostEqual(row["log_loss"], round(-__import__("math").log(0.5), 6), places=5)
        self.assertEqual(row["correct_1x2"], 1)
        self.assertEqual(evaluation.evaluate_finished(self.conn), 0)   # pas de double évaluation

    def test_saved_analyses_query(self):
        self.assertEqual(queries.list_saved_analyses(self.conn), [])


if __name__ == "__main__":
    unittest.main()
