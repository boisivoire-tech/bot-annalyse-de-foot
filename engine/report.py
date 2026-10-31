"""Rapport d'analyse d'un match en 13 sections, en français.

Chaque section contient un titre et des lignes de texte. Aucune affirmation n'est présentée comme certaine.
"""
import sqlite3
from datetime import datetime, timezone

from database import db
from engine import prediction
from engine.form_analysis import compute_form
from engine.team_analysis import head_to_head

CONFIDENCE_TEXT = {
    "insuffisant": "Données insuffisantes : analyse limitée.",
    "moyen": "Données moyennes : analyse exploitable avec réserves.",
    "complet": "Données complètes : analyse statistique plus solide.",
}


def fmt(value: float | None, digits: int = 2) -> str:
    """Nombre au format français (virgule), ou 'n.d.' si absent."""
    if value is None:
        return "n.d."
    return f"{value:.{digits}f}".replace(".", ",")


def pct(value: float) -> str:
    return f"{value * 100:.1f} %".replace(".", ",")


def _form_line(form) -> str:
    if form.sample == 0:
        return "aucun match exploitable"
    return (f"{form.sample} matchs : {form.wins} V, {form.draws} N, {form.losses} D ; "
            f"buts {form.goals_for}-{form.goals_against} ; {form.points} pts ; suite : {form.results}")


def _standing_line(conn, competition_id, season, team_id) -> str:
    if season is None:
        return "classement non disponible"
    rows = db.get_standings(conn, competition_id, season)
    for row in rows:
        if row["team_id"] == team_id:
            diff = row["goals_for"] - row["goals_against"]
            return (f"{row['rank']}e du classement, {row['points']} pts en {row['played']} matchs "
                    f"(diff. buts {diff:+d})")
    return "classement non disponible"


def build_report(conn, match_id: int, save: bool | None = None) -> dict:
    """Construit le rapport complet. Retourne {'sections': [...], 'result': PredictionResult, 'saved': bool}."""
    data = prediction.load_match_inputs(conn, match_id)
    match = data["match"]
    home_id, away_id = data["home_id"], data["away_id"]
    home_name = conn.execute("SELECT name FROM teams WHERE id = ?", (home_id,)).fetchone()[0]
    away_name = conn.execute("SELECT name FROM teams WHERE id = ?", (away_id,)).fetchone()[0]
    comp = conn.execute("SELECT name, country FROM competitions WHERE id = ?",
                        (match["competition_id"],)).fetchone()

    kickoff = datetime.fromisoformat(match["kickoff_utc"])
    now = datetime.now(timezone.utc)
    if save is None:
        save = kickoff > now          # on n'enregistre qu'avant le coup d'envoi
    saved = False
    try:
        _, result = prediction.predict_for_match(conn, match_id, save=save)
        saved = save
    except sqlite3.IntegrityError:    # analyse déjà verrouillée : on affiche sans modifier
        result = prediction.compute_for_match(conn, match_id)

    hm, am = data["home_matches"], data["away_matches"]
    h15 = compute_form(hm, home_id, 15)
    a15 = compute_form(am, away_id, 15)
    h_home = compute_form(hm, home_id, 15, "home")
    a_away = compute_form(am, away_id, 15, "away")
    sections = []

    # 1. Présentation
    status_fr = {"scheduled": "à venir", "live": "en cours", "finished": "terminé",
                 "postponed": "reporté", "cancelled": "annulé", "other": "autre"}[match["status"]]
    score = ""
    if match["home_goals"] is not None and match["away_goals"] is not None:
        score = f" ; score : {match['home_goals']}-{match['away_goals']}"
    sections.append({"title": "1. Présentation du match", "lines": [
        f"{home_name} (domicile) contre {away_name} (extérieur)",
        f"Compétition : {comp['name']} ({comp['country'] or 'pays n.d.'}) ; journée : {match['round'] or 'n.d.'}",
        f"Coup d'envoi (UTC) : {kickoff.strftime('%d/%m/%Y %H:%M')} ; statut : {status_fr}{score}",
        f"Qualité des données : {result.data_quality}",
        f"Probabilité calculée : voir section 11 (modèle {result.model_version})",
        f"Niveau de confiance du modèle : {fmt(result.model_confidence)} sur 1 (ce n'est PAS une probabilité de victoire)",
        CONFIDENCE_TEXT[result.data_quality],
    ]})

    # 2 & 3. Équipes
    home_standing = _standing_line(conn, match["competition_id"], match["season"], home_id)
    away_standing = _standing_line(conn, match["competition_id"], match["season"], away_id)
    sections.append({"title": f"2. Analyse de l'équipe à domicile : {home_name}", "lines": [
        f"Forme (15 derniers) : {_form_line(h15)}",
        f"Classement : {home_standing}",
    ]})
    sections.append({"title": f"3. Analyse de l'équipe extérieure : {away_name}", "lines": [
        f"Forme (15 derniers) : {_form_line(a15)}",
        f"Classement : {away_standing}",
    ]})

    # 4. Comparaison
    sections.append({"title": "4. Comparaison des performances (15 derniers matchs)", "lines": [
        f"Buts marqués par match : {home_name} {fmt(h15.avg_for)} ; {away_name} {fmt(a15.avg_for)}",
        f"Buts encaissés par match : {home_name} {fmt(h15.avg_against)} ; {away_name} {fmt(a15.avg_against)}",
        f"Points par match : {home_name} {fmt(h15.points_per_game)} ; {away_name} {fmt(a15.points_per_game)}",
    ]})

    # 5 & 6. Derniers matchs
    for n, title in ((5, "5. Analyse des 5 derniers matchs"), (10, "6. Analyse des 10 derniers matchs")):
        sections.append({"title": title, "lines": [
            f"{home_name} : {_form_line(compute_form(hm, home_id, n))}",
            f"{away_name} : {_form_line(compute_form(am, away_id, n))}",
        ]})

    # 7. Domicile / extérieur
    sections.append({"title": "7. Analyse domicile / extérieur", "lines": [
        f"{home_name} à domicile : {_form_line(h_home)}",
        f"{away_name} à l'extérieur : {_form_line(a_away)}",
    ]})

    # 8. Confrontations directes
    h2h = head_to_head(data["h2h"], home_id, away_id, limit=10)
    if h2h["sample"] == 0:
        h2h_lines = ["Aucune confrontation directe enregistrée : aucun ajustement."]
    else:
        h2h_lines = [
            f"{h2h['sample']} confrontations : {home_name} {h2h['wins_a']} V, {h2h['draws']} N, "
            f"{away_name} {h2h['wins_b']} V",
            f"Buts : {home_name} {h2h['goals_a']}, {away_name} {h2h['goals_b']} "
            f"(moyenne {fmt(h2h['avg_goals_total'])} buts par match)",
            "Poids limité : au plus ±5 % sur les buts attendus.",
        ]
    sections.append({"title": "8. Confrontations directes", "lines": h2h_lines})

    # 9 & 10. Offensive et défensive
    sections.append({"title": "9. Analyse offensive", "lines": [
        f"{home_name} marque {fmt(h15.avg_for)} but(s) par match ; {away_name} marque {fmt(a15.avg_for)}.",
        "Expected Goals (xG) : non disponibles dans les données actuelles.",
    ]})
    sections.append({"title": "10. Analyse défensive", "lines": [
        f"{home_name} encaisse {fmt(h15.avg_against)} but(s) par match ; {away_name} encaisse {fmt(a15.avg_against)}.",
        f"Clean sheets : {home_name} {fmt(result.home_clean_sheet * 100, 1)} % ; "
        f"{away_name} {fmt(result.away_clean_sheet * 100, 1)} % (probabilités du modèle).",
    ]})

    # 11. Probabilités
    sections.append({"title": "11. Calcul des probabilités", "lines": [
        f"Victoire {home_name} : {pct(result.p_home)} ; match nul : {pct(result.p_draw)} ; "
        f"victoire {away_name} : {pct(result.p_away)}  (total : {result.pct_1x2[0] + result.pct_1x2[1] + result.pct_1x2[2]} %)",
        f"Buts attendus : {home_name} {fmt(result.lambda_home)} ; {away_name} {fmt(result.lambda_away)} ; "
        f"total {fmt(result.expected_total)}",
        f"Plus de 0,5 but : {pct(result.over[0.5])} ; plus de 1,5 : {pct(result.over[1.5])} ; "
        f"plus de 2,5 : {pct(result.over[2.5])} ; plus de 3,5 : {pct(result.over[3.5])}",
        f"Moins de 2,5 buts : {pct(result.under[2.5])} ; les deux équipes marquent : {pct(result.btts_yes)}",
        f"Double chance : 1X {pct(result.double_chance['1X'])} ; X2 {pct(result.double_chance['X2'])} ; "
        f"12 {pct(result.double_chance['12'])}",
    ]})

    # 12. Scores exacts
    sections.append({"title": "12. Scores exacts les plus probables", "lines": [
        f"{score_text} : {pct(p)}" for score_text, p in result.top_scores
    ]})

    # 13. Conclusion
    probs = {home_name: result.p_home, "match nul": result.p_draw, away_name: result.p_away}
    best, best_p = max(probs.items(), key=lambda kv: kv[1])
    if best_p >= 0.5:
        tendance = f"Le modèle donne l'avantage à {best} ({pct(best_p)}), sans certitude."
    elif best_p - sorted(probs.values())[1] < 0.05:
        tendance = "Le match apparaît équilibré selon le modèle : aucune issue ne se détache nettement."
    else:
        tendance = f"Issue la plus probable selon le modèle : {best} ({pct(best_p)}), avec une marge modérée."
    factors_text = [f"- {f}" for f in result.factors]
    sections.append({"title": "13. Conclusion argumentée", "lines": [
        tendance,
        CONFIDENCE_TEXT[result.data_quality],
        "Facteurs pris en compte :",
        *factors_text,
        "Ce rapport est une estimation statistique. Il ne garantit pas le résultat.",
    ]})

    return {"sections": sections, "result": result, "saved": saved,
            "home": home_name, "away": away_name}
