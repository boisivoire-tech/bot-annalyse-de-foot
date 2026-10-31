"""Probabilités dérivées de la matrice des scores, et arrondis cohérents."""
import numpy as np

OVER_LINES = (0.5, 1.5, 2.5, 3.5)


def outcome_probabilities(matrix: np.ndarray) -> tuple[float, float, float]:
    """(victoire domicile, nul, victoire extérieur). Lignes = buts domicile, colonnes = buts extérieur."""
    home_win = float(np.tril(matrix, -1).sum())
    draw = float(np.trace(matrix))
    away_win = float(np.triu(matrix, 1).sum())
    return home_win, draw, away_win


def total_goals_probability(matrix: np.ndarray, line: float, over: bool) -> float:
    """P(plus de line buts) ou P(moins de line buts)."""
    size = matrix.shape[0]
    totals = np.add.outer(np.arange(size), np.arange(size))
    mask = totals > line if over else totals < line
    return float(matrix[mask].sum())


def both_teams_to_score(matrix: np.ndarray) -> float:
    return float(matrix[1:, 1:].sum())


def home_clean_sheet(matrix: np.ndarray) -> float:
    """Le domicile ne encaisse aucun but : l'extérieur ne marque pas (colonne 0)."""
    return float(matrix[:, 0].sum())


def away_clean_sheet(matrix: np.ndarray) -> float:
    """L'extérieur ne encaisse aucun but : le domicile ne marque pas (ligne 0)."""
    return float(matrix[0, :].sum())


def home_not_scoring(matrix: np.ndarray) -> float:
    return float(matrix[0, :].sum())


def away_not_scoring(matrix: np.ndarray) -> float:
    return float(matrix[:, 0].sum())


def double_chance(home_win: float, draw: float, away_win: float) -> dict[str, float]:
    return {"1X": home_win + draw, "X2": draw + away_win, "12": home_win + away_win}


def top_scores(matrix: np.ndarray, count: int = 5) -> list[tuple[str, float]]:
    """Les scores exacts les plus probables, du plus probable au moins probable."""
    flat = np.argsort(matrix, axis=None)[::-1][:count]
    result = []
    for index in flat:
        i, j = np.unravel_index(index, matrix.shape)
        result.append((f"{i}-{j}", float(matrix[i, j])))
    return result


def round_to_total(values: list[float], total: int = 100) -> list[int]:
    """Arrondit des pourcentages en entiers dont la somme vaut exactement `total` (méthode du plus fort reste)."""
    if not values or sum(values) <= 0:
        raise ValueError("valeurs invalides")
    scaled = [v / sum(values) * total for v in values]
    floors = [int(np.floor(v)) for v in scaled]
    remainder = total - sum(floors)
    order = sorted(range(len(values)), key=lambda k: scaled[k] - floors[k], reverse=True)
    for k in order[:remainder]:
        floors[k] += 1
    return floors
