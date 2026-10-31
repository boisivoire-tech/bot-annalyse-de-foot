"""Requêtes de lecture utilisées par les pages de l'interface."""


def list_matches(conn, date_from: str, date_to: str, team: str = "", competition_id: int | None = None,
                 country: str = "", status: str | None = None, limit: int = 300) -> list[dict]:
    """Matchs entre deux dates UTC (incluses dans [date_from, date_to[), avec filtres facultatifs."""
    sql = """SELECT m.id, m.kickoff_utc, m.status, m.home_goals, m.away_goals, m.round,
                    c.id AS competition_id, c.name AS competition, c.country AS country,
                    h.name AS home, a.name AS away
             FROM matches m
             JOIN competitions c ON c.id = m.competition_id
             JOIN teams h ON h.id = m.home_team_id
             JOIN teams a ON a.id = m.away_team_id
             WHERE m.kickoff_utc >= ? AND m.kickoff_utc < ?"""
    params: list = [date_from, date_to]
    if team:
        sql += " AND (h.name LIKE ? OR a.name LIKE ?)"
        params += [f"%{team}%", f"%{team}%"]
    if competition_id is not None:
        sql += " AND c.id = ?"
        params.append(competition_id)
    if country:
        sql += " AND c.country = ?"
        params.append(country)
    if status:
        sql += " AND m.status = ?"
        params.append(status)
    sql += " ORDER BY m.kickoff_utc LIMIT ?"
    params.append(limit)
    return [dict(r) for r in db_rows(conn, sql, params)]


def list_competitions(conn) -> list[dict]:
    return [dict(r) for r in db_rows(conn, "SELECT id, name, country FROM competitions ORDER BY name", [])]


def list_countries(conn) -> list[str]:
    rows = db_rows(conn, "SELECT DISTINCT country FROM competitions WHERE country IS NOT NULL ORDER BY country", [])
    return [r[0] for r in rows]


def list_teams(conn, search: str = "", limit: int = 200) -> list[dict]:
    sql = "SELECT id, api_id, name, country FROM teams"
    params: list = []
    if search:
        sql += " WHERE name LIKE ?"
        params.append(f"%{search}%")
    sql += " ORDER BY name LIMIT ?"
    params.append(limit)
    return [dict(r) for r in db_rows(conn, sql, params)]


def list_saved_analyses(conn, limit: int = 200) -> list[dict]:
    """Analyses enregistrées avec le match et, si terminé, le résultat réel."""
    sql = """SELECT a.id, a.created_at, a.p_home, a.p_draw, a.p_away, a.most_likely_score,
                    a.data_quality, a.model_confidence, a.is_locked, a.match_id,
                    m.kickoff_utc, m.status, m.home_goals, m.away_goals,
                    h.name AS home, aw.name AS away, c.name AS competition,
                    e.correct_1x2, e.brier_1x2
             FROM analyses a
             JOIN matches m ON m.id = a.match_id
             JOIN teams h ON h.id = m.home_team_id
             JOIN teams aw ON aw.id = m.away_team_id
             JOIN competitions c ON c.id = m.competition_id
             LEFT JOIN evaluations e ON e.analysis_id = a.id
             ORDER BY a.created_at DESC LIMIT ?"""
    return [dict(r) for r in db_rows(conn, sql, [limit])]


def count_upcoming(conn, now_iso: str) -> int:
    return db_rows(conn, "SELECT COUNT(*) FROM matches WHERE status = 'scheduled' AND kickoff_utc >= ?",
                   [now_iso])[0][0]


def db_rows(conn, sql: str, params: list):
    return conn.execute(sql, params).fetchall()
