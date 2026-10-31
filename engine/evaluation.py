"""Auto-évaluation du modèle : résultats réels contre prédictions enregistrées.

Métriques (plus le score est bas, meilleur il est) :
- Brier 1X2 = somme sur les 3 issues de (probabilité prédite - résultat réel 0/1)^2. Parfait = 0.
- Log loss = -ln(probabilité donnée à l'issue réelle). Plus il est bas, mieux c'est.
- Précision = part des matchs où l'issue la plus probable s'est réalisée.
"""
import math
from collections import defaultdict

from database.db import utc_now

EPS = 1e-15
BINARY_MARKETS = {  # marché : (colonne de probabilité, fonction qui dit si l'événement a eu lieu)
    "Plus de 0,5 but": ("p_over_05", lambda h, a: h + a > 0.5),
    "Plus de 1,5 but": ("p_over_15", lambda h, a: h + a > 1.5),
    "Plus de 2,5 buts": ("p_over_25", lambda h, a: h + a > 2.5),
    "Plus de 3,5 buts": ("p_over_35", lambda h, a: h + a > 3.5),
    "Les deux équipes marquent": ("p_btts", lambda h, a: h > 0 and a > 0),
}


def _log_loss(p: float) -> float:
    return -math.log(max(p, EPS))


def lock_started_matches(conn, now_iso: str | None = None) -> int:
    """Verrouille les analyses dont le match a déjà commencé. Retourne le nombre verrouillé."""
    now = now_iso or utc_now()
    with conn:
        cursor = conn.execute(
            """UPDATE analyses SET is_locked = 1
               WHERE is_locked = 0 AND match_id IN (SELECT id FROM matches WHERE kickoff_utc <= ?)""",
            (now,),
        )
    return cursor.rowcount


def evaluate_finished(conn) -> int:
    """Évalue toutes les analyses dont le match est terminé et n'a pas encore été évalué."""
    rows = conn.execute(
        """SELECT a.id, a.p_home, a.p_draw, a.p_away, a.p_over_05, a.p_over_15, a.p_over_25,
                  a.p_over_35, a.p_btts, m.home_goals, m.away_goals
           FROM analyses a JOIN matches m ON m.id = a.match_id
           WHERE m.status = 'finished' AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
             AND a.id NOT IN (SELECT analysis_id FROM evaluations)"""
    ).fetchall()
    count = 0
    with conn:
        for r in rows:
            h, a = r["home_goals"], r["away_goals"]
            actual = "H" if h > a else ("D" if h == a else "A")
            probs = {"H": r["p_home"], "D": r["p_draw"], "A": r["p_away"]}
            outcomes = {k: 1 if k == actual else 0 for k in probs}
            brier = sum((probs[k] - outcomes[k]) ** 2 for k in probs)
            predicted = max(probs, key=probs.get)
            conn.execute(
                """INSERT INTO evaluations (analysis_id, actual_home_goals, actual_away_goals, actual_result,
                       brier_1x2, log_loss, correct_1x2, evaluated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (r["id"], h, a, actual, round(brier, 6), round(_log_loss(probs[actual]), 6),
                 1 if predicted == actual else 0, utc_now()),
            )
            for market, (column, happened) in BINARY_MARKETS.items():
                p = r[column]
                if p is None:
                    continue
                o = 1 if happened(h, a) else 0
                conn.execute(
                    """INSERT INTO evaluation_markets (analysis_id, market, predicted_prob, actual, brier, log_loss)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (r["id"], market, p, o, round((p - o) ** 2, 6),
                     round(-(o * math.log(max(p, EPS)) + (1 - o) * math.log(max(1 - p, EPS))), 6)),
                )
            count += 1
    return count


def performance_summary(conn) -> dict:
    """Indicateurs globaux, par championnat et par catégorie de prédiction."""
    analyses = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    matches_analyzed = conn.execute("SELECT COUNT(DISTINCT match_id) FROM analyses").fetchone()[0]
    rows = conn.execute(
        """SELECT e.correct_1x2, e.brier_1x2, e.log_loss, c.name AS competition
           FROM evaluations e
           JOIN analyses a ON a.id = e.analysis_id
           JOIN matches m ON m.id = a.match_id
           JOIN competitions c ON c.id = m.competition_id"""
    ).fetchall()
    n = len(rows)
    by_comp = defaultdict(list)
    for r in rows:
        by_comp[r["competition"]].append(r)

    def agg(items):
        k = len(items)
        return {
            "count": k,
            "accuracy": round(sum(i["correct_1x2"] for i in items) / k, 3) if k else None,
            "brier": round(sum(i["brier_1x2"] for i in items) / k, 4) if k else None,
            "log_loss": round(sum(i["log_loss"] for i in items) / k, 4) if k else None,
        }

    market_rows = conn.execute(
        "SELECT market, predicted_prob, actual, brier, log_loss FROM evaluation_markets").fetchall()
    by_market = defaultdict(list)
    for r in market_rows:
        by_market[r["market"]].append(r)
    markets = {}
    for name, items in by_market.items():
        k = len(items)
        markets[name] = {
            "count": k,
            "accuracy": round(sum(1 for i in items
                                  if (i["predicted_prob"] >= 0.5) == (i["actual"] == 1)) / k, 3),
            "brier": round(sum(i["brier"] for i in items) / k, 4),
            "log_loss": round(sum(i["log_loss"] for i in items) / k, 4),
        }

    return {
        "analyses": analyses,
        "matches_analyzed": matches_analyzed,
        "evaluated": n,
        "overall": agg(rows),
        "by_competition": {name: agg(items) for name, items in sorted(by_comp.items())},
        "by_market": markets,
    }
