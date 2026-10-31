"""Analyse de la forme récente d'une équipe.

Entrée : une liste de matchs terminés, sous forme de dictionnaires
(home_team_id, away_team_id, home_goals, away_goals, kickoff_utc). Les identifiants sont les identifiants locaux.
Sortie : un résumé chiffré. Aucune donnée n'est inventée : si l'échantillon est trop petit, le nombre réel est indiqué.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FormSummary:
    requested: int | None      # nombre demandé (None = tous les matchs disponibles)
    sample: int                # nombre de matchs réellement utilisés
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    points: int
    results: str               # 'V' victoire, 'N' nul, 'D' défaite ; du plus récent au plus ancien
    avg_for: float | None      # buts marqués par match
    avg_against: float | None  # buts encaissés par match
    points_per_game: float | None
    win_rate: float | None     # entre 0 et 1

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against


def _outcome(match: dict, team_id: int):
    """Retourne (résultat, buts marqués, buts encaissés, joue à domicile) pour une équipe."""
    is_home = match["home_team_id"] == team_id
    goals_for = match["home_goals"] if is_home else match["away_goals"]
    goals_against = match["away_goals"] if is_home else match["home_goals"]
    if goals_for > goals_against:
        result = "V"
    elif goals_for == goals_against:
        result = "N"
    else:
        result = "D"
    return result, goals_for, goals_against, is_home


def is_usable(match: dict) -> bool:
    """Un match est utilisable s'il a un score complet."""
    return match.get("home_goals") is not None and match.get("away_goals") is not None


def compute_form(matches: list[dict], team_id: int, n: int | None = None,
                 venue: str | None = None) -> FormSummary:
    """Calcule la forme sur les n derniers matchs (venue = 'home', 'away' ou None pour les deux)."""
    if venue not in (None, "home", "away"):
        raise ValueError("venue doit valoir 'home', 'away' ou None")

    selected = []
    for match in sorted(matches, key=lambda m: m["kickoff_utc"], reverse=True):
        if not is_usable(match) or team_id not in (match["home_team_id"], match["away_team_id"]):
            continue
        _, _, _, is_home = _outcome(match, team_id)
        if venue == "home" and not is_home:
            continue
        if venue == "away" and is_home:
            continue
        selected.append(match)
        if n is not None and len(selected) >= n:
            break

    wins = draws = losses = gf = ga = 0
    letters = []
    for match in selected:
        result, goals_for, goals_against, _ = _outcome(match, team_id)
        letters.append(result)
        gf += goals_for
        ga += goals_against
        if result == "V":
            wins += 1
        elif result == "N":
            draws += 1
        else:
            losses += 1

    sample = len(selected)
    points = 3 * wins + draws
    return FormSummary(
        requested=n,
        sample=sample,
        wins=wins,
        draws=draws,
        losses=losses,
        goals_for=gf,
        goals_against=ga,
        points=points,
        results="".join(letters),
        avg_for=round(gf / sample, 2) if sample else None,
        avg_against=round(ga / sample, 2) if sample else None,
        points_per_game=round(points / sample, 2) if sample else None,
        win_rate=round(wins / sample, 3) if sample else None,
    )
