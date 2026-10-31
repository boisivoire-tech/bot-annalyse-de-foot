"""Client de l'API API-Football (api-sports.io).

- Lit la clé dans le fichier .env (jamais écrite dans le code).
- Vérifie chaque réponse avant de l'utiliser.
- Transforme les données brutes en dictionnaires simples, plus faciles à enregistrer.
"""
from datetime import date, datetime, timezone

import requests

from config import API_FOOTBALL_BASE_URL, API_FOOTBALL_KEY, REQUEST_TIMEOUT_SECONDS

PROVIDER = "API-Football"

# Codes de statut de l'API -> statuts internes (correspondent à la contrainte SQL de la table matches)
STATUS_MAP = {
    "NS": "scheduled", "TBD": "scheduled",
    "1H": "live", "HT": "live", "2H": "live", "ET": "live", "BT": "live",
    "P": "live", "LIVE": "live", "INT": "live", "SUSP": "live",
    "FT": "finished", "AET": "finished", "PEN": "finished", "AWD": "finished", "WO": "finished",
    "PST": "postponed",
    "CANC": "cancelled", "ABD": "cancelled",
}


class ApiError(Exception):
    """Erreur lisible par l'utilisateur (connexion, clé, quota, réponse invalide)."""


def _to_int_or_none(value):
    return None if value is None else int(value)


def normalize_fixture(item: dict) -> dict:
    """Vérifie et simplifie un match brut. Lève ValueError si des champs indispensables manquent."""
    try:
        fixture = item["fixture"]
        league = item["league"]
        home = item["teams"]["home"]
        away = item["teams"]["away"]
        goals = item.get("goals") or {}
        kickoff = datetime.fromisoformat(fixture["date"]).astimezone(timezone.utc)
        short_status = fixture["status"]["short"]
        return {
            "api_id": int(fixture["id"]),
            "kickoff_utc": kickoff.replace(microsecond=0).isoformat(),
            "status": STATUS_MAP.get(short_status, "other"),
            "round": league.get("round"),
            "league": {
                "api_id": int(league["id"]),
                "name": str(league["name"]),
                "country": league.get("country"),
                "season": _to_int_or_none(league.get("season")),
            },
            "home": {"api_id": int(home["id"]), "name": str(home["name"])},
            "away": {"api_id": int(away["id"]), "name": str(away["name"])},
            "home_goals": _to_int_or_none(goals.get("home")),
            "away_goals": _to_int_or_none(goals.get("away")),
        }
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Match incomplet dans la réponse API : {exc}") from exc


class FootballApiClient:
    def __init__(self, api_key: str = API_FOOTBALL_KEY, base_url: str = API_FOOTBALL_BASE_URL,
                 session=None, timeout: int = REQUEST_TIMEOUT_SECONDS):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.requests_remaining: str | None = None
        self.last_skipped = 0

    def _get(self, endpoint: str, params: dict) -> list:
        if not self.api_key:
            raise ApiError("Clé API absente : renseignez API_FOOTBALL_KEY dans le fichier .env.")
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.session.get(url, params=params,
                                        headers={"x-apisports-key": self.api_key},
                                        timeout=self.timeout)
        except requests.RequestException as exc:
            raise ApiError("Connexion impossible à l'API. Vérifiez votre Internet.") from exc

        if response.status_code == 429:
            raise ApiError("Limite de requêtes atteinte. Réessayez plus tard.")
        if response.status_code in (401, 403):
            raise ApiError("Clé API refusée. Vérifiez API_FOOTBALL_KEY dans le fichier .env.")
        if response.status_code != 200:
            raise ApiError(f"Erreur HTTP {response.status_code} de l'API.")

        try:
            data = response.json()
        except ValueError as exc:
            raise ApiError("Réponse de l'API illisible (JSON attendu).") from exc

        errors = data.get("errors")
        if errors:  # l'API renvoie [] ou {} quand tout va bien
            raise ApiError(f"L'API a signalé une erreur : {errors}")

        self.requests_remaining = response.headers.get("x-ratelimit-requests-remaining")
        payload = data.get("response")
        if not isinstance(payload, list):
            raise ApiError("Structure de réponse inattendue de l'API.")
        return payload

    def fixtures_by_date(self, day: date, league_id: int | None = None,
                         season: int | None = None) -> list[dict]:
        """Matchs d'une date donnée, normalisés. Les matchs invalides sont ignorés et comptés."""
        params = {"date": day.isoformat()}
        if league_id:
            params["league"] = league_id
        if season:
            params["season"] = season
        raw = self._get("fixtures", params)
        fixtures, skipped = [], 0
        for item in raw:
            try:
                fixtures.append(normalize_fixture(item))
            except ValueError:
                skipped += 1
        self.last_skipped = skipped
        return fixtures
