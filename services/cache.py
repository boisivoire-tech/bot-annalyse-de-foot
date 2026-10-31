"""Cache local dans SQLite (table api_cache).

Évite les appels API inutiles et permet de consulter les dernières données hors connexion.
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

from database.db import utc_now


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get(conn: sqlite3.Connection, key: str, allow_expired: bool = False):
    """Retourne la valeur en cache, ou None si absente ou expirée (sauf si allow_expired=True)."""
    row = conn.execute(
        "SELECT payload, expires_at FROM api_cache WHERE cache_key = ?", (key,)
    ).fetchone()
    if row is None:
        return None
    expired = datetime.fromisoformat(row["expires_at"]) <= _now()
    if expired and not allow_expired:
        return None
    return json.loads(row["payload"])


def set(conn: sqlite3.Connection, key: str, value, source: str, ttl_seconds: int) -> None:
    """Enregistre une valeur JSON-sérialisable avec sa durée de validité."""
    expires_at = (_now() + timedelta(seconds=ttl_seconds)).replace(microsecond=0).isoformat()
    with conn:
        conn.execute(
            """INSERT INTO api_cache (cache_key, payload, source, fetched_at, expires_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(cache_key) DO UPDATE SET
                   payload = excluded.payload, source = excluded.source,
                   fetched_at = excluded.fetched_at, expires_at = excluded.expires_at""",
            (key, json.dumps(value, ensure_ascii=False), source, utc_now(), expires_at),
        )
