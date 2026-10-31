"""Gestionnaire de données : relie l'API, le cache et la base SQLite.

Ordre de lecture : cache valide -> API (si besoin) -> dernières données locales si Internet manque.
Toutes les écritures sont faites dans une seule transaction, sans doublons.
"""
from dataclasses import dataclass
from datetime import date

from config import CACHE_TTL_HOURS
from database import db
from services import cache
from services.football_api import PROVIDER, ApiError, FootballApiClient


@dataclass
class SyncResult:
    count: int = 0
    from_cache: bool = False
    offline: bool = False        # données anciennes utilisées car l'API est injoignable
    error: str | None = None


class DataManager:
    def __init__(self, conn, client: FootballApiClient, ttl_seconds: int = CACHE_TTL_HOURS * 3600):
        self.conn = conn
        self.client = client
        self.ttl_seconds = ttl_seconds

    # ----- Chargement avec cache ------------------------------------------
    def _load(self, key: str, endpoint: str, fetch, force: bool = False):
        """Retourne (données, résultat). Essaie le cache, puis l'API, puis les données expirées."""
        result = SyncResult()
        if not force:
            data = cache.get(self.conn, key)
            if data is not None:
                result.from_cache = True
                return data, result
        try:
            data = fetch()
        except ApiError as exc:
            db.record_sync(self.conn, PROVIDER, endpoint, "error", str(exc))
            result.error = str(exc)
            data = cache.get(self.conn, key, allow_expired=True)
            if data is None:
                return None, result
            result.offline = True
            result.from_cache = True
            return data, result
        cache.set(self.conn, key, data, PROVIDER, self.ttl_seconds)
        db.record_sync(self.conn, PROVIDER, endpoint, "ok")
        return data, result

    # ----- Synchronisations -------------------------------------------------
    def sync_fixtures_for_date(self, day: date, force: bool = False) -> SyncResult:
        fixtures, result = self._load(
            f"fixtures:{day.isoformat()}", f"fixtures:{day}",
            lambda: self.client.fixtures_by_date(day), force)
        if fixtures is not None:
            result.count = self._store_fixtures(fixtures)
        return result

    def sync_team_history(self, team_api_id: int, last: int = 15, force: bool = False) -> SyncResult:
        """Récupère et enregistre les derniers matchs d'une équipe."""
        fixtures, result = self._load(
            f"team_last:{team_api_id}:{last}", f"team:{team_api_id}:last{last}",
            lambda: self.client.team_last_fixtures(team_api_id, last), force)
        if fixtures is not None:
            result.count = self._store_fixtures(fixtures)
        return result

    def sync_head_to_head(self, team_a: int, team_b: int, last: int = 10, force: bool = False) -> SyncResult:
        """Récupère et enregistre les confrontations directes."""
        fixtures, result = self._load(
            f"h2h:{team_a}-{team_b}:{last}", f"h2h:{team_a}-{team_b}",
            lambda: self.client.head_to_head_fixtures(team_a, team_b, last), force)
        if fixtures is not None:
            result.count = self._store_fixtures(fixtures)
        return result

    def sync_standings(self, league_id: int, season: int, force: bool = False) -> SyncResult:
        """Récupère et enregistre le classement d'un championnat."""
        data, result = self._load(
            f"standings:{league_id}:{season}", f"standings:{league_id}:{season}",
            lambda: self.client.standings(league_id, season), force)
        if data is not None and data.get("league"):
            result.count = self._store_standings(data)
        return result

    # ----- Écritures -------------------------------------------------------
    def _store_fixtures(self, fixtures: list[dict]) -> int:
        stored = 0
        with self.conn:
            for fx in fixtures:
                league = fx["league"]
                comp_id = db.upsert_competition(self.conn, league["api_id"], league["name"],
                                                league["country"], league["season"], None, PROVIDER)
                home_id = db.upsert_team(self.conn, fx["home"]["api_id"], fx["home"]["name"], None, PROVIDER)
                away_id = db.upsert_team(self.conn, fx["away"]["api_id"], fx["away"]["name"], None, PROVIDER)
                if home_id == away_id:
                    continue  # donnée incohérente : ignorée
                db.upsert_match(self.conn, fx["api_id"], comp_id, league["season"], fx["round"],
                                fx["kickoff_utc"], fx["status"], home_id, away_id,
                                fx["home_goals"], fx["away_goals"], PROVIDER)
                stored += 1
        return stored

    def _store_standings(self, data: dict) -> int:
        league = data["league"]
        stored = 0
        with self.conn:
            comp_id = db.upsert_competition(self.conn, league["api_id"], league["name"],
                                            league["country"], league["season"], "league", PROVIDER)
            for row in data["rows"]:
                team_id = db.upsert_team(self.conn, row["team"]["api_id"], row["team"]["name"], None, PROVIDER)
                db.upsert_standing(self.conn, comp_id, league["season"], team_id, row, PROVIDER)
                stored += 1
        return stored
