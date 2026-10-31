"""Tests du moteur statistique : calculs vérifiés à la main sur des matchs connus."""
import tempfile
import unittest

from pathlib import Path

from database import db
from engine.form_analysis import compute_form
from engine.team_analysis import build_team_profile, head_to_head, quality_label
from services.data_manager import DataManager
from services.football_api import FootballApiClient, normalize_standings

T1, T2, T3, T4, T5, T6 = 1, 2, 3, 4, 5, 6


def m(day, home, away, hg, ag):
    return {"kickoff_utc": f"2026-11-{day:02d}T15:00:00+00:00", "home_team_id": home,
            "away_team_id": away, "home_goals": hg, "away_goals": ag}


# Matchs de l'équipe 1, du plus récent au plus ancien
MATCHES = [
    m(10, T1, T2, 2, 0),   # domicile, victoire 2-0
    m(9, T3, T1, 1, 1),    # extérieur, nul 1-1
    m(8, T1, T4, 0, 3),    # domicile, défaite 0-3
    m(7, T5, T1, 2, 1),    # extérieur, défaite 2-1
    m(6, T1, T6, 3, 1),    # domicile, victoire 3-1
]


class FormTests(unittest.TestCase):
    def test_last_5_form(self):
        f = compute_form(MATCHES, T1, 5)
        self.assertEqual((f.sample, f.wins, f.draws, f.losses), (5, 2, 1, 2))
        self.assertEqual((f.goals_for, f.goals_against, f.points), (7, 7, 7))
        self.assertEqual(f.results, "VNDDV")
        self.assertEqual(f.avg_for, 1.4)
        self.assertEqual(f.points_per_game, 1.4)

    def test_requesting_more_than_available_does_not_invent_matches(self):
        f = compute_form(MATCHES, T1, 15)
        self.assertEqual(f.sample, 5)
        self.assertEqual(f.requested, 15)

    def test_home_only(self):
        f = compute_form(MATCHES, T1, 15, "home")
        self.assertEqual((f.sample, f.wins, f.losses), (3, 2, 1))
        self.assertEqual((f.goals_for, f.goals_against), (5, 4))

    def test_away_only(self):
        f = compute_form(MATCHES, T1, 15, "away")
        self.assertEqual((f.sample, f.draws, f.losses), (2, 1, 1))

    def test_empty_sample_gives_no_averages(self):
        f = compute_form([], T1, 5)
        self.assertEqual(f.sample, 0)
        self.assertIsNone(f.avg_for)
        self.assertIsNone(f.win_rate)

    def test_unfinished_matches_are_ignored(self):
        pending = {"kickoff_utc": "2026-11-11T15:00:00+00:00", "home_team_id": T1,
                   "away_team_id": T2, "home_goals": None, "away_goals": None}
        self.assertEqual(compute_form([pending] + MATCHES, T1, 15).sample, 5)

    def test_invalid_venue_raises(self):
        with self.assertRaises(ValueError):
            compute_form(MATCHES, T1, 5, "neutre")


class ProfileAndH2HTests(unittest.TestCase):
    def test_quality_labels(self):
        self.assertEqual(quality_label(3), "insuffisant")
        self.assertEqual(quality_label(7), "moyen")
        self.assertEqual(quality_label(12), "complet")

    def test_profile_contains_all_windows(self):
        profile = build_team_profile(MATCHES, T1)
        self.assertEqual(set(profile["overall"]), {5, 10, 15})
        self.assertEqual(profile["overall"][10].sample, 5)
        self.assertEqual(profile["quality"], "moyen")  # 5 matchs : seuil moyen

    def test_head_to_head_counts_both_sides(self):
        meetings = MATCHES + [m(1, T2, T1, 0, 1)]     # 2 reçoit 1, victoire de 1 (2-0 le 10 nov.)
        h2h = head_to_head(meetings, T1, T2, limit=10)
        self.assertEqual(h2h["sample"], 2)
        self.assertEqual((h2h["wins_a"], h2h["wins_b"], h2h["draws"]), (2, 0, 0))
        self.assertEqual((h2h["goals_a"], h2h["goals_b"]), (3, 0))

    def test_head_to_head_empty(self):
        self.assertEqual(head_to_head(MATCHES, T1, T5)["sample"], 1)  # T5 a joué une fois contre T1


class StandingsNormalizeTests(unittest.TestCase):
    PAYLOAD = [{"league": {"id": 39, "name": "Premier League", "country": "England", "season": 2026,
                           "standings": [[
                               {"rank": 1, "team": {"id": 33, "name": "MU"}, "points": 21,
                                "all": {"played": 9, "win": 7, "draw": 0, "lose": 2,
                                        "goals": {"for": 20, "against": 10}}},
                               {"rank": "x", "team": {"id": 1, "name": "bad"}, "points": 0,
                                "all": {}},
                           ]]}}]

    def test_rows_normalized_and_invalid_skipped(self):
        data = normalize_standings(self.PAYLOAD)
        self.assertEqual(data["league"]["api_id"], 39)
        self.assertEqual(len(data["rows"]), 1)
        self.assertEqual(data["rows"][0]["points"], 21)


class StorageTests(unittest.TestCase):
    """Chemin complet : réponses simulées -> base -> calcul."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self._tmp.name) / "t.db")

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    @staticmethod
    def _fixture(fid, day, home, away, hg, ag):
        return {"api_id": fid, "kickoff_utc": f"2026-11-{day:02d}T15:00:00+00:00", "status": "finished",
                "round": "R", "league": {"api_id": 39, "name": "PL", "country": "England", "season": 2026},
                "home": {"api_id": home, "name": f"Equipe {home}"},
                "away": {"api_id": away, "name": f"Equipe {away}"},
                "home_goals": hg, "away_goals": ag}

    def test_history_is_stored_and_read_back_for_calculation(self):
        from tests.test_football_api import FakeResponse, FakeSession
        raw = [{"fixture": {"id": 500 + i, "date": f"2026-11-{i+1:02d}T15:00:00+00:00",
                            "status": {"short": "FT"}},
                "league": {"id": 39, "name": "PL", "country": "England", "season": 2026, "round": "R"},
                "teams": {"home": {"id": 33, "name": "MU"}, "away": {"id": 40 + i, "name": f"A{i}"}},
                "goals": {"home": 2, "away": 1}} for i in range(3)]
        session = FakeSession(FakeResponse(data={"errors": [], "response": raw}))
        manager = DataManager(self.conn, FootballApiClient(api_key="K", session=session))
        result = manager.sync_team_history(33, last=15)
        self.assertEqual(result.count, 3)
        local = db.get_local_team_id(self.conn, 33)
        self.assertIsNotNone(local)
        matches = db.get_finished_matches(self.conn, local)
        self.assertEqual(len(matches), 3)
        form = compute_form(matches, local, 5)
        self.assertEqual((form.wins, form.losses), (3, 0))

    def test_standings_stored_and_ordered(self):
        from tests.test_engine_stats import StandingsNormalizeTests
        from tests.test_football_api import FakeResponse, FakeSession
        session = FakeSession(FakeResponse(data={"errors": [], "response": StandingsNormalizeTests.PAYLOAD}))
        manager = DataManager(self.conn, FootballApiClient(api_key="K", session=session))
        self.assertEqual(manager.sync_standings(39, 2026).count, 1)
        comp = self.conn.execute("SELECT id FROM competitions WHERE api_id = 39").fetchone()[0]
        rows = db.get_standings(self.conn, comp, 2026)
        self.assertEqual(rows[0]["team_name"], "MU")
        self.assertEqual(rows[0]["points"], 21)


if __name__ == "__main__":
    unittest.main()
