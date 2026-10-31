"""Moteur de prédiction : calcule les buts attendus puis les probabilités des résultats.

Principe (modèle de Poisson "force d'attaque / force de défense") :
- Buts attendus domicile  = attaque du domicile (à domicile) x défense de l'extérieur (à l'extérieur) x moyenne de référence domicile
- Buts attendus extérieur = attaque de l'extérieur (à l'extérieur) x défense du domicile (à domicile) x moyenne de référence extérieur
- Les forces sont "ramenées vers 1" si l'échantillon est petit (shrinkage), pour ne pas surréagir à 2 ou 3 matchs.
- La forme récente et les confrontations directes ajustent légèrement les résultats (bornes strictes).
- Les xG, blessures et compositions ne sont utilisés que s'ils sont disponibles et confirmés. Sinon, ils sont signalés comme absents.

Ce moteur donne des PROBABILITÉS, jamais des certitudes.
"""
import json
from dataclasses import dataclass, field

from database import db
from engine import poisson, probability
from engine.form_analysis import compute_form
from engine.team_analysis import quality_label

MODEL_VERSION = "poisson-v1"
DEFAULT_HOME_GOALS = 1.45      # moyenne de référence utilisée si le championnat n'a pas assez de données
DEFAULT_AWAY_GOALS = 1.15
MIN_LEAGUE_MATCHES = 20        # en dessous, on utilise la référence par défaut
SHRINK_K = 5                   # poids de la référence (1.0) face à l'échantillon réel
MIN_VENUE_SAMPLE = 3           # minimum de matchs à domicile/extérieur pour utiliser le split
LAMBDA_MIN, LAMBDA_MAX = 0.2, 4.5
FORM_FACTOR_LIMIT = 0.10       # la forme récente modifie au plus de ±10 %
H2H_FACTOR_LIMIT = 0.05        # les confrontations directes modifient au plus de ±5 %
QUALITY_ORDER = ["insuffisant", "moyen", "complet"]


@dataclass
class PredictionResult:
    model_version: str
    lambda_home: float
    lambda_away: float
    p_home: float
    p_draw: float
    p_away: float
    pct_1x2: tuple[int, int, int]
    over: dict[float, float]
    under: dict[float, float]
    btts_yes: float
    btts_no: float
    home_clean_sheet: float
    away_clean_sheet: float
    home_not_scoring: float
    away_not_scoring: float
    double_chance: dict[str, float]
    top_scores: list[tuple[str, float]]
    truncated_mass: float
    data_quality: str
    model_confidence: float
    factors: list[str] = field(default_factory=list)
    inputs: dict = field(default_factory=dict)

    @property
    def expected_total(self) -> float:
        return self.lambda_home + self.lambda_away


def _shrink(ratio: float, sample: int) -> float:
    """Ramène un ratio vers 1 quand l'échantillon est petit."""
    return (sample * ratio + SHRINK_K) / (sample + SHRINK_K)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def league_baseline(home_avg: float | None, away_avg: float | None, matches: int) -> tuple[float, float, bool]:
    """Moyennes de référence (domicile, extérieur) et indication de leur origine."""
    if matches >= MIN_LEAGUE_MATCHES and home_avg and away_avg:
        return home_avg, away_avg, True
    return DEFAULT_HOME_GOALS, DEFAULT_AWAY_GOALS, False


def predict_match(home_matches: list[dict], away_matches: list[dict], home_id: int, away_id: int,
                  baseline: tuple[float, float, bool] = (DEFAULT_HOME_GOALS, DEFAULT_AWAY_GOALS, False),
                  h2h_matches: list[dict] | None = None) -> PredictionResult:
    """Calcule toutes les probabilités d'un match à partir de l'historique des deux équipes.

    home_matches / away_matches : matchs terminés de chaque équipe, AVANT le match analysé.
    """
    base_home, base_away, has_league = baseline
    factors: list[str] = []
    inputs: dict = {"baseline_home": base_home, "baseline_away": base_away,
                    "league_baseline_from_data": has_league}

    if not has_league:
        factors.append("Moyennes de référence du championnat par défaut (données de championnat insuffisantes).")

    # --- Forces offensives et défensives ---------------------------------
    h_all = compute_form(home_matches, home_id, 15)
    a_all = compute_form(away_matches, away_id, 15)
    h_venue = compute_form(home_matches, home_id, 15, "home")
    a_venue = compute_form(away_matches, away_id, 15, "away")

    h_use = h_venue if h_venue.sample >= MIN_VENUE_SAMPLE else h_all
    a_use = a_venue if a_venue.sample >= MIN_VENUE_SAMPLE else a_all
    h_label = "à domicile" if h_use is h_venue else "toutes rencontres (échantillon domicile trop petit)"
    a_label = "à l'extérieur" if a_use is a_venue else "toutes rencontres (échantillon extérieur trop petit)"

    if h_use.sample == 0 or a_use.sample == 0:
        attack_home = defense_home = attack_away = defense_away = 1.0
        factors.append("Aucun historique exploitable : le modèle utilise la moyenne de référence seule.")
    else:
        attack_home = _shrink(h_use.avg_for / base_home, h_use.sample)
        defense_away = _shrink(a_use.avg_against / base_home, a_use.sample)
        attack_away = _shrink(a_use.avg_for / base_away, a_use.sample)
        defense_home = _shrink(h_use.avg_against / base_away, h_use.sample)
        factors.append(
            f"Attaque domicile ({h_label}) : {h_use.avg_for} buts marqués par match "
            f"sur {h_use.sample} matchs.")
        factors.append(
            f"Défense extérieur ({a_label}) : {a_use.avg_against} buts encaissés par match "
            f"sur {a_use.sample} matchs.")
        factors.append(
            f"Attaque extérieur ({a_label}) : {a_use.avg_for} buts marqués par match "
            f"sur {a_use.sample} matchs.")
        factors.append(
            f"Défense domicile ({h_label}) : {h_use.avg_against} buts encaissés par match "
            f"sur {h_use.sample} matchs.")

    lam_home = attack_home * defense_away * base_home
    lam_away = attack_away * defense_home * base_away

    # --- Forme récente (5 derniers vs 15 derniers, points par match) -----
    def form_factor(matches, team_id):
        f5 = compute_form(matches, team_id, 5)
        f15 = compute_form(matches, team_id, 15)
        if not f5.sample or not f15.sample or not f15.points_per_game:
            return 1.0, None
        ratio = f5.points_per_game / f15.points_per_game
        return _clip(1 + 0.5 * (ratio - 1), 1 - FORM_FACTOR_LIMIT, 1 + FORM_FACTOR_LIMIT), f5.results

    fh, fh_results = form_factor(home_matches, home_id)
    fa, fa_results = form_factor(away_matches, away_id)
    lam_home *= fh
    lam_away *= fa
    inputs["form_factor_home"], inputs["form_factor_away"] = round(fh, 3), round(fa, 3)
    if fh_results is not None and fa_results is not None:
        factors.append(f"Forme récente (5 derniers matchs) : domicile {fh_results}, extérieur {fa_results}.")
    else:
        factors.append("Forme récente : historique insuffisant pour l'ajustement.")

    # --- Confrontations directes (poids limité) --------------------------
    h2h_factor = 1.0
    h2h_count = len(h2h_matches or [])
    if h2h_count >= 2:
        goals = [(m["home_goals"] + m["away_goals"]) for m in h2h_matches]
        h2h_avg = sum(goals) / len(goals)
        weight = min(h2h_count, 5) / 5
        raw = 1 + weight * (h2h_avg / (base_home + base_away) - 1)
        h2h_factor = _clip(raw, 1 - H2H_FACTOR_LIMIT, 1 + H2H_FACTOR_LIMIT)
        factors.append(f"Confrontations directes : {h2h_count} matchs, moyenne de {h2h_avg:.2f} buts par match.")
    else:
        factors.append("Confrontations directes : moins de 2 matchs, aucun ajustement.")
    lam_home *= h2h_factor
    lam_away *= h2h_factor
    inputs["h2h_factor"] = round(h2h_factor, 3)

    factors.append("xG, tirs et corners : non utilisés (données absentes ou non vérifiées pour ce match).")
    factors.append("Absences et compositions : non intégrées (aucune source confirmée).")

    lam_home = _clip(lam_home, LAMBDA_MIN, LAMBDA_MAX)
    lam_away = _clip(lam_away, LAMBDA_MIN, LAMBDA_MAX)

    # --- Probabilités -----------------------------------------------------
    matrix, truncated = poisson.score_matrix(lam_home, lam_away)
    ph, pd, pa = probability.outcome_probabilities(matrix)
    pct = probability.round_to_total([ph, pd, pa], 100)

    # --- Qualité des données et confiance du modèle ----------------------
    quality = min(
        quality_label(min(h_all.sample, 15)), quality_label(min(a_all.sample, 15)),
        key=QUALITY_ORDER.index,
    )
    confidence = {"insuffisant": 0.30, "moyen": 0.55, "complet": 0.75}[quality]
    if not has_league:
        confidence -= 0.10
    if h2h_count < 2:
        confidence -= 0.02
    confidence = round(_clip(confidence, 0.10, 0.90), 2)

    inputs.update({"home_sample": h_all.sample, "away_sample": a_all.sample,
                   "h2h_sample": h2h_count, "lambda_home": round(lam_home, 3),
                   "lambda_away": round(lam_away, 3)})

    return PredictionResult(
        model_version=MODEL_VERSION,
        lambda_home=round(lam_home, 3),
        lambda_away=round(lam_away, 3),
        p_home=ph, p_draw=pd, p_away=pa,
        pct_1x2=tuple(pct),
        over={line: probability.total_goals_probability(matrix, line, True) for line in probability.OVER_LINES},
        under={line: probability.total_goals_probability(matrix, line, False) for line in probability.OVER_LINES},
        btts_yes=probability.both_teams_to_score(matrix),
        btts_no=1 - probability.both_teams_to_score(matrix),
        home_clean_sheet=probability.home_clean_sheet(matrix),
        away_clean_sheet=probability.away_clean_sheet(matrix),
        home_not_scoring=probability.home_not_scoring(matrix),
        away_not_scoring=probability.away_not_scoring(matrix),
        double_chance=probability.double_chance(ph, pd, pa),
        top_scores=probability.top_scores(matrix, 5),
        truncated_mass=truncated,
        data_quality=quality,
        model_confidence=confidence,
        factors=factors,
        inputs=inputs,
    )


def predict_for_match(conn, match_id: int) -> tuple[int, PredictionResult]:
    """Charge un match depuis la base, calcule la prédiction, l'enregistre et retourne (id analyse, résultat).

    Seuls les matchs joués AVANT le coup d'envoi servent de données (aucune fuite du résultat).
    """
    match = conn.execute(
        "SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    if match is None:
        raise ValueError(f"Match introuvable : {match_id}")
    kickoff = match["kickoff_utc"]
    home_id, away_id = match["home_team_id"], match["away_team_id"]

    def before(matches):
        return [m for m in matches if m["kickoff_utc"] < kickoff]

    home_matches = before(db.get_finished_matches(conn, home_id))
    away_matches = before(db.get_finished_matches(conn, away_id))
    h2h = before(db.get_finished_matches(conn, home_id, opponent_id=away_id))

    avg_home, avg_away, count = db.competition_goal_averages(conn, match["competition_id"], match["season"])
    baseline = league_baseline(avg_home, avg_away, count)

    result = predict_match(home_matches, away_matches, home_id, away_id, baseline, h2h)

    values = {
        "lambda_home": result.lambda_home, "lambda_away": result.lambda_away,
        "p_home": result.p_home, "p_draw": result.p_draw, "p_away": result.p_away,
        "p_over_05": result.over[0.5], "p_over_15": result.over[1.5],
        "p_over_25": result.over[2.5], "p_over_35": result.over[3.5],
        "p_btts": result.btts_yes,
        "most_likely_score": result.top_scores[0][0],
        "data_quality": result.data_quality,
        "model_confidence": result.model_confidence,
        "inputs_json": json.dumps({"factors": result.factors, "inputs": result.inputs},
                                                ensure_ascii=False),
    }
    with conn:
        analysis_id = db.save_analysis(conn, match_id, MODEL_VERSION, values)
    return analysis_id, result
