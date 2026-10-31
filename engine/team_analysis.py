"""Profil statistique d'une équipe et confrontations directes."""
from engine.form_analysis import compute_form, is_usable

WINDOWS = (5, 10, 15)        # fenêtres de forme demandées par le cahier des charges
VENUE_WINDOW = 15            # nombre de matchs utilisé pour les performances domicile/extérieur


def quality_label(sample: int) -> str:
    """Qualité des données, selon le nombre de matchs disponibles."""
    if sample < 5:
        return "insuffisant"
    if sample < 10:
        return "moyen"
    return "complet"


def build_team_profile(matches: list[dict], team_id: int) -> dict:
    """Résume la forme d'une équipe : fenêtres 5/10/15, domicile, extérieur."""
    overall = {n: compute_form(matches, team_id, n) for n in WINDOWS}
    everything = compute_form(matches, team_id)
    return {
        "team_id": team_id,
        "sample": everything.sample,
        "quality": quality_label(everything.sample),
        "overall": overall,
        "home": compute_form(matches, team_id, VENUE_WINDOW, "home"),
        "away": compute_form(matches, team_id, VENUE_WINDOW, "away"),
    }


def head_to_head(matches: list[dict], team_a: int, team_b: int, limit: int = 10) -> dict:
    """Bilan des confrontations directes entre deux équipes (les plus récentes d'abord)."""
    meetings = [
        m for m in sorted(matches, key=lambda m: m["kickoff_utc"], reverse=True)
        if is_usable(m) and {m["home_team_id"], m["away_team_id"]} == {team_a, team_b}
    ][:limit]

    wins_a = draws = wins_b = goals_a = goals_b = 0
    for m in meetings:
        if m["home_team_id"] == team_a:
            ga, gb = m["home_goals"], m["away_goals"]
        else:
            ga, gb = m["away_goals"], m["home_goals"]
        goals_a += ga
        goals_b += gb
        if ga > gb:
            wins_a += 1
        elif ga == gb:
            draws += 1
        else:
            wins_b += 1

    sample = len(meetings)
    return {
        "sample": sample,
        "quality": quality_label(sample),
        "wins_a": wins_a,
        "draws": draws,
        "wins_b": wins_b,
        "goals_a": goals_a,
        "goals_b": goals_b,
        "avg_goals_total": round((goals_a + goals_b) / sample, 2) if sample else None,
    }


def find_standing(rows: list[dict], team_id: int) -> dict | None:
    """Ligne du classement pour une équipe (rows = lignes du classement, avec team_id local)."""
    for row in rows:
        if row["team_id"] == team_id:
            return row
    return None
