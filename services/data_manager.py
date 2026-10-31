"""Gestionnaire de données : relie l'API, le cache et la base SQLite.

Ordre de lecture : cache valide -> API (si besoin) -> base locale hors connexion.
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

    def sync_fixtures_for_date(self, day: date, force: bool = False) -> SyncResult:
        key = f"fixtures:{day.isoformat()}"
        fixtures = None if force else cache.get(self.conn, key)
        result = SyncResult(from_cache=fixtures is not None)

        if fixtures is None:
            try:
                fixtures = self.client.fixtures_by_date(day)
            except ApiError as exc:
                db.record_sync(self.conn, PROVIDER, f"fixtures:{day}", "error", str(exc))
                result.error = str(exc)
                fixtures = cache.get(self.conn, key, allow_expired=True)
                if fixtures is None:
                    return result          # rien à afficher
                result.offline = True
                result.from_cache = True
            else:
                cache.set(self.conn, key, fixtures, PROVIDER, self.ttl_seconds)
                db.record_sync(self.conn, PROVIDER, f"fixtures:{day}", "ok")

        result.count = self._store_fixtures(fixtures)
        return result

    def _store_fixtures(self, fixtures: list[dict]) -> int:
        """Enregistre les matchs sans doublons. Une seule transaction pour aller plus vite."""
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
        return len(fixtures)
