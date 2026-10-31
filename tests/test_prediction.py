"""Tests du moteur de prédiction : cohérence mathématique et enregistrement en base."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np

from database import db
from engine import poisson, probability
from engine.prediction import predict_for_match, predict_match, league_baseline


def m(day, home, away, hg, ag):
    return {"kickoff_utc": f"2026-10-{day:02d}T15:00:00+00:00", "home_team_id": home,
            "away_team_id": away, "home_goals": hg, "away_goals": ag}


STRONG_HOME = [m(d, 1, 10 + d, 3, 0) for d in range(1, 11)]          # équipe 1 gagne tout à domicile
STRONG_HOME_AWAY = [m(d, 20 + d, 1, 0, 2) for d in range(1, 11)]     # équipe 1 gagne tout à l'extérieur
WEAK_AWAY = [m(d, 30 + d, 2, 2, 0) for d in range(1, 11)]            # équipe 2 perd à l'extérieur
WEAK_AWAY_HOME = [m(d, 2, 40 + d, 0, 3) for d in range(1, 11)]       # équipe 2 perd à domicile


class PoissonTests(unittest.TestCase):
    def test_pmf_matches_known_value(self):
        pmf = poisson.poisson_pmf(1.0)
        self.assertAlmostEqual(pmf[0], np.exp(-1), places=10)
        self.assertAlmostEqual(pmf[1], np.exp(-1), places=10)

    def test_score_matrix_sums_to_one(self):
        matrix, truncated = poisson.score_matrix(1.6, 1.1)
        self.assertAlmostEqual(float(matrix.sum()), 1.0, places=12)
        self.assertLess(truncated, 1e-4)

    def test_invalid_lambda_rejected(self):
        with self.assertRaises(ValueError):
            poisson.poisson_pmf(0)


class ProbabilityTests(unittest.TestCase):
    def setUp(self):
        self.matrix, _ = poisson.score_matrix(1.5, 1.2)

    def test_1x2_sums_to_one(self):
        ph, pd, pa = probability.outcome_probabilities(self.matrix)
        self.assertAlmostEqual(ph + pd + pa, 1.0, places=10)

    def test_equal_lambdas_give_symmetric_home_away(self):
        matrix, _ = poisson.score_matrix(1.3, 1.3)
        ph, _, pa = probability.outcome_probabilities(matrix)
        self.assertAlmostEqual(ph, pa, places=12)

    def test_over_under_are_complementary(self):
        for line in (0.5, 1.5, 2.5, 3.5):
            over = probability.total_goals_probability(self.matrix, line, True)
            under = probability.total_goals_probability(self.matrix, line, False)
            self.assertAlmostEqual(over + under, 1.0, places=10)

    def test_over_05_equals_one_minus_0_0(self):
        over = probability.total_goals_probability(self.matrix, 0.5, True)
        self.assertAlmostEqual(over, 1 - self.matrix[0, 0], places=12)

    def test_btts_and_clean_sheets_consistent(self):
        btts = probability.both_teams_to_score(self.matrix)
        self.assertAlmostEqual(btts, 1 - probability.home_not_scoring(self.matrix)
                               - probability.away_not_scoring(self.matrix)
                               + self.matrix[0, 0], places=12)
        self.assertAlmostEqual(probability.home_clean_sheet(self.matrix),
                               probability.away_not_scoring(self.matrix), places=12)

    def test_double_chance(self):
        dc = probability.double_chance(0.5, 0.3, 0.2)
        self.assertAlmostEqual(dc["1X"], 0.8)
        self.assertAlmostEqual(dc["X2"], 0.5)
        self.assertAlmostEqual(dc["12"], 0.7)

    def test_top_scores_sorted(self):
        top = probability.top_scores(self.matrix, 5)
        probs = [p for _, p in top]
        self.assertEqual(probs, sorted(probs, reverse=True))
        self.assertEqual(len(top), 5)

    def test_round_to_total_always_100(self):
        for values in ([0.333, 0.333, 0.334], [0.5, 0.25, 0.25], [0.1, 0.2, 0.7], [0.45, 0.27, 0.28]):
            self.assertEqual(sum(probability.round_to_total(values, 100)), 100)


class PredictionTests(unittest.TestCase):
    def test_1x2_percentages_always_sum_to_100(self):
        for lam_h, lam_a in ((0.3, 0.3), (1.0, 2.5), (2.2, 0.6), (1.45, 1.15)):
            matrix, _ = poisson.score_matrix(lam_h, lam_a)
            pct = probability.round_to_total(list(probability.outcome_probabilities(matrix)), 100)
            self.assertEqual(sum(pct), 100)

    def test_stronger_team_is_favourite(self):
        result = predict_match(STRONG_HOME, WEAK_AWAY_HOME + [], 1, 2)
        self.assertGreater(result.p_home, result.p_away)
        self.assertGreater(result.lambda_home, result.lambda_away)

    def test_no_history_gives_low_confidence_and_explanations(self):
        result = predict_match([], [], 1, 2)
        self.assertEqual(result.data_quality, "insuffisant")
        self.assertLessEqual(result.model_confidence, 0.25)
        self.assertTrue(any("Aucun historique" in f for f in result.factors))
        self.assertTrue(any("Absences" in f for f in result.factors))

    def test_probabilities_are_not_certainties(self):
        result = predict_match(STRONG_HOME, WEAK_AWAY_HOME, 1, 2)
        for p in (result.p_home, result.p_draw, result.p_away):
            self.assertTrue(0 < p < 1)

    def test_lambda_stays_within_bounds(self):
        extreme = [m(d, 1, 50 + d, 9, 0) for d in range(1, 11)]
        result = predict_match(extreme, [], 1, 2)
        self.assertLessEqual(result.lambda_home, 4.5)
        self.assertGreaterEqual(result.lambda_away, 0.2)

    def test_league_baseline_falls_back_when_few_matches(self):
        self.assertFalse(league_baseline(1.6, 1.2, 5)[2])
        self.assertTrue(league_baseline(1.6, 1.2, 50)[2])

    def test_markets_are_coherent(self):
        result = predict_match(STRONG_HOME, WEAK_AWAY, 1, 2)
        self.assertAlmostEqual(result.btts_yes + result.btts_no, 1.0, places=10)
        self.assertGreaterEqual(result.over[0.5], result.over[1.5])
        self.assertGreaterEqual(result.over[1.5], result.over[2.5])
        self.assertAlmostEqual(result.double_chance["1X"], result.p_home + result.p_draw, places=10)


class DatabasePredictionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self._tmp.name) / "p.db")
        self.comp = db.upsert_competition(self.conn, 39, "PL", "England", 2026, "league", "test")
        self.home = db.upsert_team(self.conn, 1, "A", None, "test")
        self.away = db.upsert_team(self.conn, 2, "B", None, "test")
        self.future = db.upsert_match(self.conn, 900, self.comp, 2026, "R", "2026-11-01T15:00:00+00:00",
                                      "scheduled", self.home, self.away, None, None, "test")
        # Historique des deux équipes, avant le match
        for i in range(6):
            opp_home = db.upsert_team(self.conn, 100 + i, f"Adv{i}", None, "test")
            opp_away = db.upsert_team(self.conn, 200 + i, f"Adv2{i}", None, "test")
            db.upsert_match(self.conn, 1000 + i, self.comp, 2026, "R", f"2026-10-{i+1:02d}T15:00:00+00:00",
                            "finished", self.home, opp_home, 2, 0, "test")
            db.upsert_match(self.conn, 2000 + i, self.comp, 2026, "R", f"2026-10-{i+1:02d}T17:00:00+00:00",
                            "finished", opp_away, self.away, 1, 1, "test")
        # Match après le coup d'envoi : ne doit JAMAIS être utilisé
        db.upsert_match(self.conn, 3000, self.comp, 2026, "R", "2026-11-05T15:00:00+00:00",
                        "finished", self.home, self.away, 9, 9, "test")

    def tearDown(self):
        self.conn.close()
        self._tmp.cleanup()

    def test_prediction_saved_and_updated_without_duplicate(self):
        analysis_id, result = predict_for_match(self.conn, self.future)
        again_id, _ = predict_for_match(self.conn, self.future)
        self.assertEqual(analysis_id, again_id)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0], 1)
        self.assertEqual(sum(result.pct_1x2), 100)

    def test_future_result_is_never_used(self):
        _, result = predict_for_match(self.conn, self.future)
        # Le match 9-9 du 5 novembre (après le coup d'envoi) est exclu : 6 matchs seulement
        self.assertEqual(result.inputs["home_sample"], 6)
        self.assertEqual(result.inputs["away_sample"], 6)
        self.assertEqual(result.inputs["h2h_sample"], 0)

    def test_locked_prediction_cannot_change(self):
        analysis_id, _ = predict_for_match(self.conn, self.future)
        db.lock_analyses_for_match(self.conn, self.future)
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            predict_for_match(self.conn, self.future)


if __name__ == "__main__":
    unittest.main()
