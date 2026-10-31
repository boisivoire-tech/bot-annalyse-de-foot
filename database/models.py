"""Schéma SQLite de FOOTBALL INTELLIGENCE PRO et types de données.

Conventions :
- Les probabilités sont stockées entre 0 et 1 (0,55 = 55 %).
- Chaque donnée externe porte une colonne `source` et une colonne `updated_at` (UTC, ISO 8601).
- Une analyse verrouillée (`is_locked = 1`, début du match) ne peut plus être modifiée ni supprimée :
  c'est garanti par des déclencheurs SQLite, pas seulement par le code Python.
"""
from dataclasses import dataclass
from datetime import datetime

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS competitions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    api_id        INTEGER NOT NULL UNIQUE,
    name          TEXT    NOT NULL,
    country       TEXT,
    season        INTEGER,
    kind          TEXT,                       -- 'league' ou 'cup'
    source        TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS teams (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    api_id        INTEGER NOT NULL UNIQUE,
    name          TEXT    NOT NULL,
    country       TEXT,
    source        TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    api_id          INTEGER NOT NULL UNIQUE,
    competition_id  INTEGER NOT NULL REFERENCES competitions(id),
    season          INTEGER,
    round           TEXT,
    kickoff_utc     TEXT    NOT NULL,
    status          TEXT    NOT NULL CHECK (status IN ('scheduled', 'live', 'finished', 'postponed', 'cancelled', 'other')),
    home_team_id    INTEGER NOT NULL REFERENCES teams(id),
    away_team_id    INTEGER NOT NULL REFERENCES teams(id),
    home_goals      INTEGER CHECK (home_goals IS NULL OR home_goals >= 0),
    away_goals      INTEGER CHECK (away_goals IS NULL OR away_goals >= 0),
    source          TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    CHECK (home_team_id <> away_team_id)
);
CREATE INDEX IF NOT EXISTS idx_matches_kickoff ON matches(kickoff_utc);
CREATE INDEX IF NOT EXISTS idx_matches_competition ON matches(competition_id, season);
CREATE INDEX IF NOT EXISTS idx_matches_home ON matches(home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away ON matches(away_team_id);

-- Statistiques avancées par équipe et par match : colonnes NULL si la source ne les fournit pas
CREATE TABLE IF NOT EXISTS match_stats (
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    team_id         INTEGER NOT NULL REFERENCES teams(id),
    shots           INTEGER,
    shots_on_target INTEGER,
    corners         INTEGER,
    possession      REAL,
    xg              REAL,
    xga             REAL,
    big_chances     INTEGER,
    clean_sheet     INTEGER CHECK (clean_sheet IS NULL OR clean_sheet IN (0, 1)),
    source          TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    PRIMARY KEY (match_id, team_id)
);

CREATE TABLE IF NOT EXISTS standings (
    competition_id  INTEGER NOT NULL REFERENCES competitions(id),
    season          INTEGER NOT NULL,
    team_id         INTEGER NOT NULL REFERENCES teams(id),
    rank            INTEGER NOT NULL,
    points          INTEGER NOT NULL,
    played          INTEGER NOT NULL,
    won             INTEGER NOT NULL,
    drawn           INTEGER NOT NULL,
    lost            INTEGER NOT NULL,
    goals_for       INTEGER NOT NULL,
    goals_against   INTEGER NOT NULL,
    source          TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    PRIMARY KEY (competition_id, season, team_id)
);

-- Analyses enregistrées (une par match et par version du modèle : pas de doublon)
CREATE TABLE IF NOT EXISTS analyses (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id          INTEGER NOT NULL REFERENCES matches(id),
    model_version     TEXT    NOT NULL,
    created_at        TEXT    NOT NULL,
    lambda_home       REAL    NOT NULL,
    lambda_away       REAL    NOT NULL,
    p_home            REAL    NOT NULL CHECK (p_home BETWEEN 0 AND 1),
    p_draw            REAL    NOT NULL CHECK (p_draw BETWEEN 0 AND 1),
    p_away            REAL    NOT NULL CHECK (p_away BETWEEN 0 AND 1),
    p_over_05         REAL,
    p_over_15         REAL,
    p_over_25         REAL,
    p_over_35         REAL,
    p_btts            REAL,
    most_likely_score TEXT,
    data_quality      TEXT    NOT NULL CHECK (data_quality IN ('insuffisant', 'moyen', 'complet')),
    model_confidence  REAL    CHECK (model_confidence IS NULL OR model_confidence BETWEEN 0 AND 1),
    inputs_json       TEXT,
    is_locked         INTEGER NOT NULL DEFAULT 0 CHECK (is_locked IN (0, 1)),
    UNIQUE (match_id, model_version)
);

-- Une prédiction ne peut plus être modifiée après le début du match
CREATE TRIGGER IF NOT EXISTS trg_analyses_no_update_locked
BEFORE UPDATE ON analyses
WHEN OLD.is_locked = 1
BEGIN
    SELECT RAISE(ABORT, 'Analyse verrouillee : modification interdite apres le debut du match');
END;

CREATE TRIGGER IF NOT EXISTS trg_analyses_no_delete_locked
BEFORE DELETE ON analyses
WHEN OLD.is_locked = 1
BEGIN
    SELECT RAISE(ABORT, 'Analyse verrouillee : suppression interdite');
END;

-- Résultat réel comparé à la prédiction
CREATE TABLE IF NOT EXISTS evaluations (
    analysis_id       INTEGER PRIMARY KEY REFERENCES analyses(id),
    actual_home_goals INTEGER NOT NULL,
    actual_away_goals INTEGER NOT NULL,
    actual_result     TEXT    NOT NULL CHECK (actual_result IN ('H', 'D', 'A')),
    brier_1x2         REAL    NOT NULL,
    log_loss          REAL    NOT NULL,
    correct_1x2       INTEGER NOT NULL CHECK (correct_1x2 IN (0, 1)),
    evaluated_at      TEXT    NOT NULL
);

-- Cache des réponses API (évite les appels inutiles, sert en mode hors ligne)
CREATE TABLE IF NOT EXISTS api_cache (
    cache_key   TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    source      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);

-- Journal des synchronisations (erreurs de connexion signalées)
CREATE TABLE IF NOT EXISTS sync_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    provider    TEXT NOT NULL,
    endpoint    TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    message     TEXT,
    created_at  TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Team:
    id: int
    api_id: int
    name: str
    country: str | None


@dataclass(frozen=True)
class Match:
    id: int
    api_id: int
    competition_id: int
    kickoff_utc: datetime
    status: str
    home_team_id: int
    away_team_id: int
    home_goals: int | None
    away_goals: int | None
