"""Accès à la base SQLite : connexion, création du schéma et fonctions d'enregistrement.

Toutes les écritures passent par des requêtes paramétrées (protection contre l'injection SQL)
et par des "UPSERT" (INSERT ... ON CONFLICT) qui évitent les doublons.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import DB_PATH
from database.models import SCHEMA, SCHEMA_VERSION


def utc_now() -> str:
    """Date/heure actuelle en UTC, au format ISO 8601."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Ouvre la base (la crée si besoin) avec les réglages adaptés à un PC modeste."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Crée les tables si elles n'existent pas encore. Version suivie par PRAGMA user_version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current < SCHEMA_VERSION:
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


# ----- Référentiels --------------------------------------------------------

def upsert_competition(conn, api_id: int, name: str, country: str | None,
                       season: int | None, kind: str | None, source: str) -> int:
    """Insère ou met à jour une compétition. Retourne son identifiant local."""
    row = conn.execute(
        """INSERT INTO competitions (api_id, name, country, season, kind, source, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(api_id) DO UPDATE SET
               name = excluded.name, country = excluded.country, season = excluded.season,
               kind = excluded.kind, source = excluded.source, updated_at = excluded.updated_at
           RETURNING id""",
        (api_id, name, country, season, kind, source, utc_now()),
    ).fetchone()
    return row[0]


def upsert_team(conn, api_id: int, name: str, country: str | None, source: str) -> int:
    """Insère ou met à jour une équipe. Retourne son identifiant local."""
    row = conn.execute(
        """INSERT INTO teams (api_id, name, country, source, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(api_id) DO UPDATE SET
               name = excluded.name, country = excluded.country,
               source = excluded.source, updated_at = excluded.updated_at
           RETURNING id""",
        (api_id, name, country, source, utc_now()),
    ).fetchone()
    return row[0]


def upsert_match(conn, api_id: int, competition_id: int, season: int | None, round_name: str | None,
                 kickoff_utc: str, status: str, home_team_id: int, away_team_id: int,
                 home_goals: int | None, away_goals: int | None, source: str) -> int:
    """Insère ou met à jour un match. Retourne son identifiant local."""
    row = conn.execute(
        """INSERT INTO matches (api_id, competition_id, season, round, kickoff_utc, status,
                                home_team_id, away_team_id, home_goals, away_goals, source, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(api_id) DO UPDATE SET
               competition_id = excluded.competition_id, season = excluded.season,
               round = excluded.round, kickoff_utc = excluded.kickoff_utc, status = excluded.status,
               home_team_id = excluded.home_team_id, away_team_id = excluded.away_team_id,
               home_goals = excluded.home_goals, away_goals = excluded.away_goals,
               source = excluded.source, updated_at = excluded.updated_at
           RETURNING id""",
        (api_id, competition_id, season, round_name, kickoff_utc, status,
         home_team_id, away_team_id, home_goals, away_goals, source, utc_now()),
    ).fetchone()
    return row[0]


# ----- Analyses et évaluations ---------------------------------------------

def save_analysis(conn, match_id: int, model_version: str, values: dict) -> int:
    """Enregistre une analyse. `values` contient les probabilités et paramètres du modèle.

    Si l'analyse existe déjà et n'est pas verrouillée, elle est mise à jour.
    Si elle est verrouillée, le déclencheur SQLite refuse la modification.
    """
    columns = ["lambda_home", "lambda_away", "p_home", "p_draw", "p_away",
               "p_over_05", "p_over_15", "p_over_25", "p_over_35", "p_btts",
               "most_likely_score", "data_quality", "model_confidence", "inputs_json"]
    missing = [c for c in ("lambda_home", "lambda_away", "p_home", "p_draw", "p_away", "data_quality")
               if c not in values]
    if missing:
        raise ValueError(f"Champs obligatoires manquants : {missing}")
    params = [values.get(c) for c in columns]
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(f"{c} = excluded.{c}" for c in columns)
    row = conn.execute(
        f"""INSERT INTO analyses (match_id, model_version, created_at, {", ".join(columns)})
            VALUES (?, ?, ?, {placeholders})
            ON CONFLICT(match_id, model_version) DO UPDATE SET {updates}
            RETURNING id""",
        [match_id, model_version, utc_now(), *params],
    ).fetchone()
    return row[0]


def lock_analyses_for_match(conn, match_id: int) -> int:
    """Verrouille les analyses d'un match au coup d'envoi. Retourne le nombre verrouillé."""
    cursor = conn.execute(
        "UPDATE analyses SET is_locked = 1 WHERE match_id = ? AND is_locked = 0", (match_id,)
    )
    return cursor.rowcount


def record_sync(conn, provider: str, endpoint: str, status: str, message: str | None = None) -> None:
    """Journalise une synchronisation (succès ou erreur de connexion)."""
    conn.execute(
        "INSERT INTO sync_log (provider, endpoint, status, message, created_at) VALUES (?, ?, ?, ?, ?)",
        (provider, endpoint, status, message, utc_now()),
    )
