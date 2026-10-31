"""Gestionnaire de données : relie l'API, le cache et la base SQLite.

Ordre de lecture : cache valide -> API (si besoin) -> dernières données locales si Internet manque.
Toutes les écritures sont faites dans une seule transaction, sans doublons.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from config import CACHE_TTL_HOURS
from database import db
from engine import evaluation
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
            result.offline = exc.network
            data = cache.get(self.conn, key, allow_expired=True)
            if data is None:
                return None, result
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


# ----- Actualisation complète (bouton ACTUALISER) ---------------------------
MAX_REQUESTS_PER_REFRESH = 40   # protège le quota gratuit (100 requêtes/jour)
MAX_TEAMS_PER_REFRESH = 20
MAX_STANDINGS_PER_REFRESH = 6


@dataclass
class RefreshReport:
    requests_used: int = 0
    matches_stored: int = 0
    analyses_locked: int = 0
    analyses_evaluated: int = 0
    offline: bool = False
    errors: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


def refresh_all(conn, client: FootballApiClient, now: datetime | None = None,
                ttl_seconds: int = CACHE_TTL_HOURS * 3600) -> RefreshReport:
    """Met à jour matchs, historiques, classements et résultats, dans la limite du quota.

    Nécessite Internet pour les nouvelles données. Sans connexion, seules les données locales sont utilisées.
    """
    now = now or datetime.now(timezone.utc)
    manager = DataManager(conn, client, ttl_seconds)
    report = RefreshReport()

    def budget_left() -> bool:
        return client.calls < MAX_REQUESTS_PER_REFRESH

    # 1. Matchs : hier (résultats), aujourd'hui et demain. Données récentes : on force la mise à jour.
    for offset in (-1, 0, 1):
        if not budget_left() or report.offline:
            break
        day = (now + timedelta(days=offset)).date()
        result = manager.sync_fixtures_for_date(day, force=True)
        report.matches_stored += result.count
        if result.error:
            report.errors.append(result.error)
        if result.offline:
            report.offline = True

    if report.offline:
        report.messages.append("Connexion impossible : seules les données enregistrées sont affichées.")
    else:
        # 2. Historique des équipes qui jouent bientôt (cache respecté)
        upcoming_until = (now + timedelta(days=3)).isoformat()
        teams = conn.execute(
            """SELECT DISTINCT t.api_id FROM matches m
               JOIN teams t ON t.id IN (m.home_team_id, m.away_team_id)
               WHERE m.status = 'scheduled' AND m.kickoff_utc BETWEEN ? AND ?
               ORDER BY t.api_id LIMIT ?""",
            (now.isoformat(), upcoming_until, MAX_TEAMS_PER_REFRESH)).fetchall()
        for row in teams:
            if not budget_left():
                report.messages.append("Limite de requêtes atteinte pour cette actualisation.")
                break
            res = manager.sync_team_history(row[0], last=15)
            report.matches_stored += res.count
            if res.error:
                report.errors.append(res.error)
                if res.offline:
                    report.offline = True
                    break

        # 3. Classements des championnats concernés
        if not report.offline:
            comps = conn.execute(
                """SELECT DISTINCT c.api_id, c.season FROM matches m
                   JOIN competitions c ON c.id = m.competition_id
                   WHERE m.status = 'scheduled' AND m.kickoff_utc BETWEEN ? AND ?
                     AND c.kind = 'league' AND c.season IS NOT NULL
                   LIMIT ?""",
                (now.isoformat(), upcoming_until, MAX_STANDINGS_PER_REFRESH)).fetchall()
            for row in comps:
                if not budget_left():
                    break
                res = manager.sync_standings(row[0], row[1])
                if res.error:
                    report.errors.append(res.error)

    # 4. Verrouillage des analyses dont le match a commencé, puis évaluation des matchs terminés
    report.analyses_locked = evaluation.lock_started_matches(conn, now.isoformat())
    report.analyses_evaluated = evaluation.evaluate_finished(conn)
    report.requests_used = client.calls
    return report
