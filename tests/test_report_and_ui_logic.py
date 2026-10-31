"""Tests du rapport d'analyse (13 sections), des requêtes d'interface et de la configuration."""
import tempfile
import unittest
from pathlib import Path

from config import mask_key, write_env_value
from database import db, queries
from engine.report import build_report, fmt, pct


class ReportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self._tmp.name) / "rep.db")
        comp = db.upsert_competition(self.conn, 39, "Premier League", "England", 2026, "league", "t")
        home = db.upsert_team(self.conn, 1, "Équipe Domicile", None, "t")
        away = db.upsert_team(self.conn, 2, "Équipe Extérieur", None, "t")
        for i in range(12):
            opp = db.upsert_team(self.conn, 100 + i, f"Adv{i}", None, "t")
            db.upsert_match(self.conn, 1000 + i, comp, 2026, "R", f"2026-09-{i + 1:02d}T15:00:00+00:00",
                            "finished", home, opp, 2, 1, "t")
            opp2 = db.upsert_team(self.conn, 200 + i, f"Bdv{i}", None, "t")
            db.upsert_match(self.conn, 2000 + i, comp, 2026, "R", f"2026-09-{i + 1:02d}T17:00:00+00:00",
                            "finished", opp2, away, 0, 1, "t")
        self.future = db.upsert_match(self.conn, 9000, comp, 2026, "R38", "2099-05-01T15:00:00+00:00",
                                      "scheduled", home, away, None, None, "t")

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_report_has_13_numbered_sections(self):
        report = build_report(self.conn, self.future)
        titles = [s["title"] for s in report["sections"]]
        self.assertEqual(len(titles), 13)
        for n, title in enumerate(titles, start=1):
            self.assertTrue(title.startswith(f"{n}. "), title)

    def test_future_match_is_saved_and_probabilities_sum_to_100(self):
        report = build_report(self.conn, self.future)
        self.assertTrue(report["saved"])
        self.assertEqual(sum(report["result"].pct_1x2), 100)
        count = self.conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        self.assertEqual(count, 1)

    def test_past_match_is_not_saved(self):
        comp_id = self.conn.execute("SELECT id FROM competitions").fetchone()[0]
        h = self.conn.execute("SELECT id FROM teams WHERE name = 'Équipe Domicile'").fetchone()[0]
        a = self.conn.execute("SELECT id FROM teams WHERE name = 'Équipe Extérieur'").fetchone()[0]
        past = db.upsert_match(self.conn, 9100, comp_id, 2026, "R1", "2020-01-01T15:00:00+00:00",
                               "scheduled", h, a, None, None, "t")
        report = build_report(self.conn, past)
        self.assertFalse(report["saved"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0], 0)

    def test_report_states_confidence_is_not_win_probability(self):
        text = " ".join(line for s in build_report(self.conn, self.future)["sections"] for line in s["lines"])
        self.assertIn("PAS une probabilité de victoire", text)
        self.assertIn("Ce rapport est une estimation", text)

    def test_french_formatting(self):
        self.assertEqual(fmt(1.5), "1,50")
        self.assertEqual(fmt(None), "n.d.")
        self.assertEqual(pct(0.4567), "45,7 %")


class QueryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self._tmp.name) / "q.db")
        comp = db.upsert_competition(self.conn, 61, "Ligue 1", "France", 2026, "league", "t")
        h = db.upsert_team(self.conn, 1, "Paris SG", "France", "t")
        a = db.upsert_team(self.conn, 2, "Marseille", "France", "t")
        db.upsert_match(self.conn, 1, comp, 2026, "R1", "2026-10-31T19:00:00+00:00", "scheduled", h, a,
                        None, None, "t")

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_search_by_team_and_country(self):
        found = queries.list_matches(self.conn, "2026-10-31T00:00:00+00:00", "2026-11-01T00:00:00+00:00",
                                     team="marseille")
        self.assertEqual(len(found), 1)
        none = queries.list_matches(self.conn, "2026-10-31T00:00:00+00:00", "2026-11-01T00:00:00+00:00",
                                    country="Espagne")
        self.assertEqual(none, [])

    def test_date_window_excludes_other_days(self):
        found = queries.list_matches(self.conn, "2026-11-01T00:00:00+00:00", "2026-11-02T00:00:00+00:00")
        self.assertEqual(found, [])


class ConfigTests(unittest.TestCase):
    def test_key_is_masked(self):
        self.assertEqual(mask_key(""), "absente")
        self.assertEqual(mask_key("abcdefghijklmnop"), "abcd…mnop")
        self.assertNotIn("efgh", mask_key("abcdefghijklmnop"))

    def test_env_value_written_and_replaced_without_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("CACHE_TTL_HOURS=6\nAPI_FOOTBALL_KEY=ancienne\n", encoding="utf-8")
            write_env_value("API_FOOTBALL_KEY", "nouvelle_cle_123", env)
            write_env_value("API_FOOTBALL_KEY", "nouvelle_cle_456", env)
            text = env.read_text(encoding="utf-8")
            self.assertEqual(text.count("API_FOOTBALL_KEY="), 1)
            self.assertIn("API_FOOTBALL_KEY=nouvelle_cle_456", text)
            self.assertIn("CACHE_TTL_HOURS=6", text)


if __name__ == "__main__":
    unittest.main()
