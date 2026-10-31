"""Tests de la base SQLite (bibliothèque standard uniquement, pas de dépendance externe)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self._tmp.name) / "test.db")
        self.comp = db.upsert_competition(self.conn, 39, "Premier League", "England", 2026, "league", "test")
        self.home = db.upsert_team(self.conn, 1, "Équipe A", "England", "test")
        self.away = db.upsert_team(self.conn, 2, "Équipe B", "England", "test")

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def _match(self, api_id=100, home=None, away=None):
        return db.upsert_match(self.conn, api_id, self.comp, 2026, "J1", "2026-11-01T15:00:00+00:00",
                               "scheduled", home or self.home, away or self.away, None, None, "test")

    def _analysis_values(self):
        return {"lambda_home": 1.4, "lambda_away": 1.1, "p_home": 0.45, "p_draw": 0.27,
                "p_away": 0.28, "data_quality": "moyen"}

    def test_upsert_team_does_not_duplicate(self):
        again = db.upsert_team(self.conn, 1, "Équipe A renommée", "England", "test")
        self.assertEqual(again, self.home)
        count = self.conn.execute("SELECT COUNT(*) FROM teams WHERE api_id = 1").fetchone()[0]
        self.assertEqual(count, 1)

    def test_match_upsert_updates_score(self):
        match_id = self._match()
        db.upsert_match(self.conn, 100, self.comp, 2026, "J1", "2026-11-01T15:00:00+00:00",
                        "finished", self.home, self.away, 2, 1, "test")
        row = self.conn.execute("SELECT status, home_goals FROM matches WHERE id = ?", (match_id,)).fetchone()
        self.assertEqual((row["status"], row["home_goals"]), ("finished", 2))

    def test_same_team_cannot_play_itself(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._match(api_id=200, home=self.home, away=self.home)

    def test_invalid_status_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO matches (api_id, competition_id, kickoff_utc, status, home_team_id, away_team_id, source, updated_at) "
                "VALUES (300, ?, 'x', 'bizarre', ?, ?, 'test', 'x')", (self.comp, self.home, self.away))

    def test_analysis_saved_once_per_model_version(self):
        match_id = self._match()
        first = db.save_analysis(self.conn, match_id, "v1", self._analysis_values())
        second = db.save_analysis(self.conn, match_id, "v1", self._analysis_values())
        self.assertEqual(first, second)
        count = self.conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        self.assertEqual(count, 1)

    def test_probabilities_must_be_between_0_and_1(self):
        match_id = self._match()
        bad = self._analysis_values() | {"p_home": 1.5}
        with self.assertRaises(sqlite3.IntegrityError):
            db.save_analysis(self.conn, match_id, "v1", bad)

    def test_locked_analysis_cannot_be_modified_or_deleted(self):
        match_id = self._match()
        analysis_id = db.save_analysis(self.conn, match_id, "v1", self._analysis_values())
        self.assertEqual(db.lock_analyses_for_match(self.conn, match_id), 1)
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("UPDATE analyses SET p_home = 0.9 WHERE id = ?", (analysis_id,))
        with self.assertRaises(sqlite3.IntegrityError):
            with self.conn:
                self.conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))

    def test_init_is_idempotent(self):
        db.init_db(self.conn)
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        from database.models import SCHEMA_VERSION
        self.assertEqual(version, SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
