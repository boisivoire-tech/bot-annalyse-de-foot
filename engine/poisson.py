"""Modèle de Poisson : probabilités de nombre de buts et matrice des scores.

Le nombre de buts d'une équipe suit une loi de Poisson de paramètre lambda (buts attendus).
En supposant les deux équipes indépendantes, la probabilité du score i-j est P(domicile=i) * P(extérieur=j).
"""
import math

import numpy as np

MAX_GOALS = 10   # au-delà de 10 buts, la probabilité est négligeable pour un match


def poisson_pmf(lam: float, max_goals: int = MAX_GOALS) -> np.ndarray:
    """P(X = k) pour k = 0..max_goals. Calcul en logarithmes pour rester stable."""
    if not lam > 0:
        raise ValueError("lambda doit être strictement positif")
    k = np.arange(max_goals + 1)
    log_factorial = np.array([math.lgamma(i + 1) for i in k])
    return np.exp(k * math.log(lam) - lam - log_factorial)


def score_matrix(lambda_home: float, lambda_away: float, max_goals: int = MAX_GOALS):
    """Retourne (matrice, masse_tronquée).

    matrice[i, j] = probabilité du score i-j (domicile i, extérieur j), normalisée à 1.
    masse_tronquée = probabilité des scores au-delà de max_goals avant normalisation (doit rester très petite).
    """
    home = poisson_pmf(lambda_home, max_goals)
    away = poisson_pmf(lambda_away, max_goals)
    matrix = np.outer(home, away)
    total = float(matrix.sum())
    return matrix / total, 1.0 - total
