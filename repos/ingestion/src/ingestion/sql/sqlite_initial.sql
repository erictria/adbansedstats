-- Initial DuckDB schema. Future changes require explicit migrations.
CREATE TABLE IF NOT EXISTS players (
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    player_short_name TEXT NOT NULL,
    external_id TEXT NOT NULL,
    slug TEXT,
    photo_url TEXT,
    PRIMARY KEY (player_id)
);

CREATE TABLE IF NOT EXISTS teams (
    team_id TEXT NOT NULL,
    team_name TEXT NOT NULL,
    external_id TEXT NOT NULL,
    slug TEXT,
    profile_url TEXT,
    logo_url TEXT,
    PRIMARY KEY (team_id)
);

CREATE TABLE IF NOT EXISTS games (
    game_id TEXT NOT NULL,
    team_id_1 TEXT NOT NULL,
    team_id_2 TEXT NOT NULL,
    external_id TEXT,
    tournament TEXT,
    competition_name TEXT,
    venue TEXT,
    scheduled_at TEXT,
    date_time_raw TEXT,
    status TEXT,
    period INTEGER,
    clock TEXT,
    team_1_score INTEGER,
    team_2_score INTEGER,
    team_1_period_scores TEXT,
    team_2_period_scores TEXT,
    source_url TEXT,
    PRIMARY KEY (game_id),
    FOREIGN KEY (team_id_1) REFERENCES teams(team_id),
    FOREIGN KEY (team_id_2) REFERENCES teams(team_id),
    CHECK (team_id_1 <> team_id_2)
);

CREATE TABLE IF NOT EXISTS game_statistics (
    game_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    player_name TEXT,
    jersey_number TEXT,
    position TEXT,
    is_starter INTEGER,
    minutes_raw TEXT,
    seconds_played INTEGER,
    points INTEGER,
    offensive_rebounds INTEGER,
    defensive_rebounds INTEGER,
    rebounds INTEGER,
    assists INTEGER,
    turnovers INTEGER,
    steals INTEGER,
    blocks INTEGER,
    personal_fouls INTEGER,
    fouls_drawn INTEGER,
    plus_minus INTEGER,
    field_goals_made INTEGER,
    field_goals_attempted INTEGER,
    field_goals_percentage REAL,
    two_pointers_made INTEGER,
    two_pointers_attempted INTEGER,
    two_pointers_percentage REAL,
    three_pointers_made INTEGER,
    three_pointers_attempted INTEGER,
    three_pointers_percentage REAL,
    four_pointers_made INTEGER,
    four_pointers_attempted INTEGER,
    four_pointers_percentage REAL,
    free_throws_made INTEGER,
    free_throws_attempted INTEGER,
    free_throws_percentage REAL,
    PRIMARY KEY (game_id, player_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    records_written INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    source TEXT NOT NULL,
    entity TEXT NOT NULL,
    external_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES ingestion_runs(run_id),
    PRIMARY KEY (source, entity, external_id)
);
